from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def main_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button("Помощь", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Мой профиль", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("Проверить медиа", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("Фото", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("ПДФ", color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()


def inline_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False, inline=True)
    keyboard.add_button("Меню", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Спросить ИИ", color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()
