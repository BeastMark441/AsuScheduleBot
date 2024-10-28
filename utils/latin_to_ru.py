from functools import lru_cache


ASCII_TO_RUSSIAN: dict[str, str] = {
        'a': 'а', 'b': 'в', 'c': 'с', 'd': 'д', 'e': 'е', 'f': 'ф',
        'g': 'г', 'h': 'х', 'i': 'и', 'j': 'й', 'k': 'к', 'l': 'л',
        'm': 'м', 'n': 'н', 'o': 'о', 'p': 'р', 'q': 'к', 'r': 'р',
        's': 'с', 't': 'т', 'u': 'у', 'v': 'в', 'w': 'в', 'x': 'х',
        'y': 'у', 'z': 'з'}

@lru_cache(maxsize=1000)
def convert_to_russian(text: str) -> str:
    """Кэшированная функция конвертации латиницы в кириллицу"""
    return ''.join(ASCII_TO_RUSSIAN.get(char.lower(), char) for char in text)