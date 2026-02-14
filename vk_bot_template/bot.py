from __future__ import annotations

import random
import ssl
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
from vk_api.upload import VkUpload

from ai_client import HuggingFaceClient
from config import load_settings
from keyboards import inline_keyboard, main_keyboard


def get_user_name(vk: vk_api.VkApiMethod, user_id: int) -> str:
    users = vk.users.get(user_ids=[user_id])
    if not users:
        return 'Пользователь'
    first_name = users[0].get('first_name', '')
    last_name = users[0].get('last_name', '')
    full_name = f'{first_name} {last_name}'.strip()
    return full_name or 'Пользователь'


def parse_attachments(message: dict[str, object]) -> dict[str, int]:
    attachments = message.get('attachments', [])
    result = {'photo': 0, 'doc': 0, 'other': 0}
    for item in attachments:
        attachment_type = item.get('type')
        if attachment_type in result:
            result[attachment_type] += 1
        else:
            result['other'] += 1
    return result


def extract_attachments(message: dict[str, object], event_object: dict[str, object]) -> list[dict[str, object]]:
    return message.get('attachments') or event_object.get('attachments') or []


# Скачивает бинарные данные файла по URL (используется для фото и PDF).
def download_photo_bytes(photo_url: str) -> bytes:
    request = Request(photo_url, headers={'User-Agent': 'Mozilla/5.0'})
    unverified_context = ssl._create_unverified_context()
    with urlopen(request, timeout=20, context=unverified_context) as response:
        return response.read()


def get_best_photo_url(photo: dict[str, object]) -> str | None:
    sizes = photo.get('sizes', [])
    if not sizes:
        return None
    best_size = max(sizes, key=lambda x: x.get('width', 0) * x.get('height', 0))
    return best_size.get('url')


# Если в событии нет прямой ссылки на фото, получаем ее через API.
def fetch_photo_url_with_api(vk: vk_api.VkApiMethod, photo: dict[str, object]) -> str | None:
    owner_id = photo.get('owner_id')
    photo_id = photo.get('id')
    if not owner_id or not photo_id:
        return None
    access_key = photo.get('access_key')

    photo_ref = f'{owner_id}_{photo_id}'
    if access_key:
        photo_ref = f'{photo_ref}_{access_key}'

    photos = vk.photos.getById(photos=[photo_ref])
    if not photos:
        return None
    full_photo = photos[0]
    return get_best_photo_url(full_photo)


# Скачивает фото-вложения из входящего сообщения в папку downloaded_photos.
def download_photos_from_message(
    vk: vk_api.VkApiMethod,
    message: dict[str, object],
    peer_id: int,
    user_id: int,
) -> int:
    attachments = message.get('attachments', [])
    if not attachments:
        return 0

    download_dir = Path(__file__).resolve().parent / 'downloaded_photos'
    download_dir.mkdir(parents=True, exist_ok=True)
    conversation_message_id = int(message.get('conversation_message_id', 0))
    saved_count = 0

    for index, attachment in enumerate(attachments, start=1):
        if attachment.get('type') != 'photo':
            continue

        photo = attachment.get('photo', {})

        photo_url = get_best_photo_url(photo) or fetch_photo_url_with_api(vk, photo)
        if not photo_url:
            continue

        suffix = Path(urlparse(photo_url).path).suffix.lower()
        extension = suffix if suffix in {'.jpg', '.jpeg', '.png', '.webp', '.gif'} else '.jpg'
        file_name = f'peer_{peer_id}_user_{user_id}_msg_{conversation_message_id}_{index}{extension}'
        target_path = download_dir / file_name

        content = download_photo_bytes(photo_url)
        target_path.write_bytes(content)
        saved_count += 1

    return saved_count


def find_demo_pdf_path() -> Path | None:
    base_dir = Path(__file__).resolve().parent
    search_dirs = [base_dir.parent, base_dir]
    for directory in search_dirs:
        files = sorted(directory.glob('*.pdf'))
        if files:
            return files[0]
    return None


def build_doc_attachment(uploaded: object) -> str | None:
    doc = uploaded.get('doc', {})
    owner_id = doc.get('owner_id')
    doc_id = doc.get('id')
    if not owner_id or not doc_id:
        return None
    access_key = doc.get('access_key')
    base = f'doc{owner_id}_{doc_id}'
    if access_key:
        return f'{base}_{access_key}'
    return base


# Отправляет в чат демонстрационный PDF-файл из папки проекта.
def send_demo_pdf(vk_session: vk_api.VkApi, vk: vk_api.VkApiMethod, peer_id: int) -> bool:
    pdf_path = find_demo_pdf_path()
    if pdf_path is None:
        send_message(
            vk,
            peer_id,
            'Не нашел PDF в папке проекта. Положите .pdf в корень проекта или в vk_bot_template.',
        )
        return False

    upload = VkUpload(vk_session)
    uploaded = upload.document_message(doc=str(pdf_path), title=pdf_path.name, peer_id=peer_id)
    attachment = build_doc_attachment(uploaded)
    if not attachment:
        send_message(vk, peer_id, 'Не удалось загрузить PDF.')
        return False
    vk.messages.send(
        peer_id=peer_id,
        random_id=random.randint(1, 2_147_483_647),
        message='Пример отправки PDF из бота.',
        attachment=attachment,
    )
    return True


# Скачивает PDF-вложения из входящего сообщения в папку downloaded_docs.
def download_pdfs_from_message(message: dict[str, object], peer_id: int, user_id: int) -> int:
    attachments = message.get('attachments', [])
    if not attachments:
        return 0

    download_dir = Path(__file__).resolve().parent / 'downloaded_docs'
    download_dir.mkdir(parents=True, exist_ok=True)
    conversation_message_id = int(message.get('conversation_message_id', 0))
    saved_count = 0

    for index, attachment in enumerate(attachments, start=1):
        if attachment.get('type') != 'doc':
            continue
        doc = attachment.get('doc', {})

        ext_lower = str(doc.get('ext', '')).lower()
        title_lower = str(doc.get('title', '')).lower()
        if ext_lower != 'pdf' and not title_lower.endswith('.pdf'):
            continue

        doc_url = doc.get('url')
        if not doc_url:
            continue

        file_name = f'peer_{peer_id}_user_{user_id}_msg_{conversation_message_id}_{index}.pdf'
        target_path = download_dir / file_name
        content = download_photo_bytes(doc_url)
        target_path.write_bytes(content)
        saved_count += 1

    return saved_count


def find_demo_image_path() -> Path | None:
    base_dir = Path(__file__).resolve().parent
    search_dirs = [base_dir.parent, base_dir]
    patterns = ('*.png', '*.jpg', '*.jpeg', '*.webp', '*.gif')
    for directory in search_dirs:
        for pattern in patterns:
            files = sorted(directory.glob(pattern))
            if files:
                return files[0]
    return None


# Отправляет в чат демонстрационное изображение из папки проекта.
def send_demo_photo(vk_session: vk_api.VkApi, vk: vk_api.VkApiMethod, peer_id: int) -> bool:
    image_path = find_demo_image_path()
    if image_path is None:
        send_message(
            vk,
            peer_id,
            'Не нашел картинку в папке проекта. Положите .png/.jpg в корень проекта или в vk_bot_template.',
        )
        return False

    upload = VkUpload(vk_session)
    uploaded = upload.photo_messages(photos=str(image_path), peer_id=peer_id)
    if not uploaded:
        send_message(vk, peer_id, 'Не удалось загрузить изображение.')
        return False

    photo = uploaded[0]
    attachment = f"photo{photo['owner_id']}_{photo['id']}"
    vk.messages.send(
        peer_id=peer_id,
        random_id=random.randint(1, 2_147_483_647), # максимум для 32-битного целого числа
        message='Пример отправки картинки из бота.',
        attachment=attachment,
    )
    return True


def send_message(
    vk: vk_api.VkApiMethod,
    peer_id: int,
    text: str,
    keyboard: str | None = None,
) -> None:
    payload = {
        'peer_id': peer_id,
        'message': text,
        'random_id': random.randint(1, 2_147_483_647), # максимум для 32-битного целого числа
    }
    if keyboard:
        payload['keyboard'] = keyboard
    vk.messages.send(**payload)


def run() -> None:
    settings = load_settings()
    session = vk_api.VkApi(token=settings.vk_group_token)
    vk = session.get_api()
    group_id = vk.groups.getById()[0]['id']
    longpoll = VkBotLongPoll(session, group_id)
    ai_client = HuggingFaceClient(
        api_token=settings.hf_api_token,
        model=settings.hf_model,
    )

    print('Бот запущен...')

    for event in longpoll.listen():
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue

        message = event.object.message
        user_id = int(message.get('from_id', 0)) # from_id - кто отправил сообщение (ID пользователя или сообщества-автора
        peer_id = int(message.get('peer_id', 0)) # peer_id - куда отправлено сообщение (диалог/беседа/ЛС)
        if user_id <= 0 or peer_id <= 0:
            continue

        text = str(message.get('text', '')).strip()
        lower_text = text.lower()
        attachments = extract_attachments(message, event.object)
        # conversation_message_id уникален только внутри одного peer_id (диалог/беседа/ЛС)
        conversation_message_id = message.get('conversation_message_id', 0) # conversation_message_id - ID сообщения в беседе (для скачивания фото и PDF)
        message_data = {
            'attachments': attachments, # attachments - вложения в сообщении (фото, документы, другие файлы)
            'conversation_message_id': conversation_message_id,
        }
        user_name = get_user_name(vk, user_id)
        saved_photos = download_photos_from_message(vk, message_data, peer_id, user_id)
        saved_pdfs = download_pdfs_from_message(message_data, peer_id, user_id)
        attachment_stats = parse_attachments(message_data)

        if saved_photos > 0:
            send_message(vk, peer_id, f'Сохранил фото из сообщения: {saved_photos} шт.')
        if saved_pdfs > 0:
            send_message(vk, peer_id, f'Сохранил PDF из сообщения: {saved_pdfs} шт.')
        if not text:
            continue

        if lower_text in {'/start', 'start', 'menu', 'меню'}:
            send_message(
                vk,
                peer_id,
                (
                    f'Привет, {user_name}! На связи тестовый бот VK.\n'
                    'Используйте кнопки, чтобы проверить клавиатуры, медиа и ИИ.'
                ),
                keyboard=main_keyboard(),
            )
            continue

        if lower_text in {'/help', 'help', 'помощь'}:
            send_message(
                vk,
                peer_id,
                (
                    'Команды:\n'
                    '- start/menu/меню: открыть основную клавиатуру\n'
                    '- user info/мой профиль: показать информацию о профиле\n'
                    '- ask ai <вопрос> или спросить ии <вопрос>: получить ответ ИИ\n'
                    '- media status/проверить медиа: показать вложения в сообщении\n'
                    '- фото: отправить пример картинки в чат\n'
                    '- pdf/пдф: отправить пример PDF в чат'
                ),
                keyboard=inline_keyboard(),
            )
            continue

        if lower_text in {'user info', '/me', 'мой профиль'}:
            users = vk.users.get(
                user_ids=[user_id],
                fields=['city', 'sex', 'bdate'],  # city - город, sex - пол, bdate - дата рождения (формат: DD.MM.YYYY)
            )
            user = users[0] if users else {}
            city = user.get('city', {}).get('title', 'не указано')
            bdate = user.get('bdate', 'не указано')
            sex_value = user.get('sex', 0)
            sex = {1: 'женский', 2: 'мужской'}.get(sex_value, 'не указано')
            send_message(
                vk,
                peer_id,
                (
                    f'Имя: {user_name}\n'
                    f'Город: {city}\n'
                    f'Дата рождения: {bdate}\n'
                    f'Пол: {sex}'
                ),
                keyboard=inline_keyboard(),
            )
            continue

        if lower_text.startswith('ask ai ') or lower_text.startswith('спросить ии '):
            question = text[7:].strip() if lower_text.startswith('ask ai ') else text[11:].strip()
            if not question:
                send_message(vk, peer_id, 'Напишите вопрос после команды: ask ai или спросить ии')
                continue
            answer = ai_client.generate(question, user_name=user_name)
            send_message(vk, peer_id, answer, keyboard=inline_keyboard())
            continue

        if lower_text in {'ask ai', '/ai', 'спросить ии'}:
            send_message(
                vk,
                peer_id,
                'Отправьте: ask ai <ваш вопрос> или спросить ии <ваш вопрос>',
                keyboard=inline_keyboard(),
            )
            continue

        if lower_text in {'media status', '/media', 'проверить медиа'}:
            send_message(
                vk,
                peer_id,
                (
                    'Сводка по вложениям:\n'
                    f"- фото: {attachment_stats['photo']}\n"
                    f"- документы: {attachment_stats['doc']}\n"
                    f"- другое: {attachment_stats['other']}\n"
                    'Отправьте фото или документ следующим сообщением для проверки.'
                ),
                keyboard=inline_keyboard(),
            )
            continue

        if lower_text in {'фото', 'photo', '/photo'}:
            send_demo_photo(session, vk, peer_id)
            continue

        if lower_text in {'pdf', '/pdf', 'пдф', 'документ'}:
            send_demo_pdf(session, vk, peer_id)
            continue

        answer = ai_client.generate(text, user_name=user_name)
        send_message(vk, peer_id, answer, keyboard=inline_keyboard())


if __name__ == '__main__':
    run()
