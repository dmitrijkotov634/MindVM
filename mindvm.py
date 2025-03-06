from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

Type = Enum("Type", ["static", "var"])


@dataclass
class Label:
    # Метка для обозначения позиции в коде
    position: int
    not_reassigned: bool = field(default=False)


class EmuChunk:
    # Список поддерживаемых выводимых символов
    CHARS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ\n ,.=")

    # Специальные константы
    NON_ZERO = [0]  # Ссылка на истинное значение
    MAIN_THREAD = 2  # Первое главное ядро
    DISABLE_THREAD = -1  # Отключение ядра

    # Операционные коды
    OP_EXIT = 0  # Завершение выполнения
    OP_SET = 1  # Установить константное значение переменной
    OP_COPY = 2  # Копировать значение переменной
    OP_ECHO = 3  # Вывести значение переменной
    OP_FLUSH = 4  # Вывести в блок сообщения текст из буфера и очистить буфер
    OP_MATH = 5  # Выполнить математическую операцию
    OP_JUMP = 6  # Условный переход, если значение по ссылке != 0
    OP_CHAR = 7  # Вывести символ
    OP_CONTROL_THREAD = 9  # Управление ядрами, в том числе изменение счетчика команд
    OP_ADD_CONST = 10  # Добавить константу к переменной
    OP_SUB_CONST = 11  # Вычесть константу из переменной
    OP_MUL_CONST = 12  # Умножить переменную на константу
    OP_JUMP_NEQ_CONST = 13  # Переход, если переменная не равна константе
    OP_JUMP_GT_CONST = 14  # Переход, если переменная больше константы
    OP_SET_4 = 15  # Установить константные значения для 4 переменных одновременно
    OP_CONST_RAND = 16  # Сгенерировать случайное число в пределах константы
    OP_GOTO_THREAD = 17  # Установка счетчика команд для другого ядра

    # Коды математических операций
    OPERATION_ADD = 0  # Сложение (+)
    OPERATION_SUB = 1  # Вычитание (-)
    OPERATION_MUL = 2  # Умножение (*)
    OPERATION_DIV = 3  # Деление (/)
    OPERATION_EQ = 4  # Равенство (==)
    OPERATION_GT = 5  # Больше чем (>)
    OPERATION_LT = 6  # Меньше чем (<)
    OPERATION_NEQ = 7  # Не равно (!=)
    OPERATION_IRAND = 8  # Сгенерировать целое случайное целое число
    OPERATION_MOD = 9  # Остаток от деления (%)

    def __init__(self, perform_math_optimization=True):
        # Словарь для хранения ссылок на числа, оптимизирующий код
        # MATH не работает с константами, поэтому ссылки на неизменяемые значения сокращают их выделение в математических операциях.
        self.static = {}

        self.data = []  # Список данных
        self.code = []  # Список байт(int)-кода

        # Заменять ли операции MATH(ссылка, константа) на более быстрые ADD_CONST, SUB_CONST, MUL_CONST
        self.perform_math_optimization = perform_math_optimization

    def append(self, *objects: int):
        """Добавление инструкций в байт-код."""
        for value in objects:
            self.code.append(value)
            if isinstance(value, int):
                # Сохранение ссылки на число для использования в store_int
                self.static[value] = len(self.code)

    def var(self, default=0) -> list[int]:
        """Создает переменную с записью значения по умолчанию."""
        self.data.append((Type.var, default))
        return [len(self.data) + 2]

    @staticmethod
    def is_var(value):
        return isinstance(value, list)

    def resolve_arg(self, value):
        """Возвращает ссылку на аргумент, в том числе переменные, и константы"""
        if self.is_var(value):
            return value[0]

        return value

    def store_char(self, value):
        """Сохраняет символ как ссылку в data"""
        return self.store_int(self.CHARS.index(value))

    def store_int(self, value):
        """Сохраняет целое значение как ссылку в data с возможным кэшированием расположения"""
        if value in self.static:
            return Label(self.static[value])  # Возвращаем ссылку, если значение уже существует в static
        for n, v in enumerate(self.data):
            if v[0] is Type.static and v[1] == value:
                v[2] += 1  # Увеличиваем счетчик ссылок
                return [n + 3]  # Возвращаем ссылку на место в data
        self.data.append([Type.static, value, 1])
        return [len(self.data) + 2]  # Возвращаем новую ссылку на только что добавленное значение

    class RefOperator:
        """Класс для работы с операциями, которые могут применяться к ссылкам."""

        def __init__(self, chunk: "EmuChunk", ref):
            self.chunk = chunk
            self.ref = ref

        def __add__(self, other):
            if EmuChunk.is_var(other):
                return self.chunk.math(self.chunk.store_int(EmuChunk.OPERATION_ADD), self.ref, other, self.ref)
            self.chunk.add_const(self.ref, other)

        def __sub__(self, other):
            if EmuChunk.is_var(other):
                return self.chunk.math(self.chunk.store_int(EmuChunk.OPERATION_SUB), self.ref, other, self.ref)
            self.chunk.sub_const(self.ref, other)

        def __mul__(self, other):
            if EmuChunk.is_var(other):
                return self.chunk.math(self.chunk.store_int(EmuChunk.OPERATION_MUL), self.ref, other, self.ref)
            self.chunk.mul_const(self.ref, other)

    def __getitem__(self, item):
        return EmuChunk.RefOperator(self, item)

    def __setitem__(self, key, value):
        if value is None:  # Пропуск вызова __setitem__ после вызова меджиков, например пропускает c[] += ... вызов __setitem__ после __add__
            return
        if self.is_var(value):
            self.copy(key, value)  # Если переменная - копируем значение
        else:
            self.set(key, value)  # Если значение статичное - устанавливаем его

    def exit(self):
        """Завершение выполнения."""
        self.append(self.OP_EXIT)

    def set(self, ref, value):
        """Устанавливает значение переменной по ссылке."""
        self.append(
            self.OP_SET,
            self.resolve_arg(ref),
            self.resolve_arg(value)
        )

    def set_4(self, ref, value, value2, value3, value4):
        """Устанавливает 4 значения для переменных одновременно."""
        self.append(
            self.OP_SET_4,
            self.resolve_arg(ref),
            self.resolve_arg(value),
            self.resolve_arg(value2),
            self.resolve_arg(value3),
            self.resolve_arg(value4),
        )

    def copy(self, ref, ref2):
        """Копирует значение из одной переменной в другую."""
        self.append(
            self.OP_COPY,
            self.resolve_arg(ref),
            self.resolve_arg(ref2)
        )

    def echo(self, ref):
        """Выводит значение переменной."""
        self.append(self.OP_ECHO, self.resolve_arg(ref))

    def print(self, text):
        """Выводит строку символов. Строка символов обязана заканчиваться -1"""
        self.append(
            self.OP_CHAR,
            *[self.resolve_arg(self.store_char(char_)) for char_ in text.upper()],
            self.resolve_arg(self.store_int(-1))
        )

    def fprint(self, *args):
        """Функция для вывода переменных, чисел и строк."""
        for arg in args:
            if self.is_var(arg):
                self.echo(arg)
            elif isinstance(arg, int):
                self.echo(self.store_int(arg))
            elif isinstance(arg, str):
                self.print(arg)
        self.flush()

    def control_thread(self, key_ref, data):
        """Управление ядрами, в том числе изменение счетчика команд"""
        self.append(
            self.OP_CONTROL_THREAD,
            self.resolve_arg(key_ref),  # Ссылка на индекс в памяти ядер
            self.resolve_arg(data)  # Статичное значение
        )

    def goto_thread(self, thread, label):
        """Установка счетчика команд для другого ядра"""
        self.append(
            self.OP_GOTO_THREAD,
            self.resolve_arg(thread),  # Ссылка на индекс в памяти ядер
            self.resolve_arg(label)  # Метка
        )

    def flush(self):
        """Вывести в блок сообщения текст из буфера и очистить буфер"""
        self.append(self.OP_FLUSH)

    def label(self,
              label: Label | None = None,
              reassign: bool = False,
              inc_thread: bool = False  #
              ):
        """Создает метку для переходов."""

        if reassign and inc_thread:
            raise ValueError("Position increment and reassign not supported")

        if label:  # Переназначить, чтобы использовать метку ранее чем она объявлена
            label.position = len(self.code) + bool(
                inc_thread)  # Увеличение позиции на 1 для счетчика команд другого ядра
            label.not_reassigned = False
        else:
            return Label(
                position=len(self.code),
                not_reassigned=reassign
            )

    def math(self, operation, first, second, result):
        """Выполняет математическую операцию."""
        if self.perform_math_optimization:
            if not self.is_var(second):
                if first == result:
                    if operation == self.OPERATION_ADD:
                        print(f"Perform ADD_CONST optimization for {first} add {second} = {result}")
                        return self.add_const(first, second)
                    elif operation == self.OPERATION_SUB:
                        print(f"Perform SUB_CONST optimization for {first} subtract {second} = {result}")
                        return self.sub_const(first, second)
                    elif operation == self.OPERATION_MUL:
                        print(f"Perform MUL_CONST optimization for {first} multiply {second} = {result}")
                        return self.mul_const(first, second)

        self.append(
            self.OP_MATH,
            self.resolve_arg(operation),
            self.resolve_arg(first),
            self.resolve_arg(second),
            self.resolve_arg(result)
        )

    def add_const(self, ref, value):
        """Добавляет константу к переменной, ссылке."""
        self.append(
            self.OP_ADD_CONST,
            self.resolve_arg(ref),
            self.resolve_arg(value)
        )

    def sub_const(self, ref, value):
        """Вычитает константу из переменной, ссылке."""
        self.append(
            self.OP_SUB_CONST,
            self.resolve_arg(ref),
            self.resolve_arg(value)
        )

    def mul_const(self, ref, value):
        """Умножает переменную на константу."""
        self.append(
            self.OP_MUL_CONST,
            self.resolve_arg(ref),
            self.resolve_arg(value)
        )

    def const_rand(self, value, ref):
        """Генерирует случайное значение в пределах заданного диапазона."""
        self.append(
            self.OP_CONST_RAND,
            self.resolve_arg(value),
            self.resolve_arg(ref)
        )

    def jump_neq_const(self, label, ref, value):
        """Условный переход, если значение переменной не равно константе."""
        self.append(
            self.OP_JUMP_NEQ_CONST,
            label,
            self.resolve_arg(ref),
            self.resolve_arg(value)
        )

    def jump_gt_const(self, label, ref, value):
        """Условный переход, если значение переменной больше константы."""
        self.append(
            self.OP_JUMP_GT_CONST,
            label,
            self.resolve_arg(ref),
            self.resolve_arg(value)
        )

    def jump(self, label, ref):
        """Условный переход, если значение по ссылке != 0"""
        self.append(
            self.OP_JUMP,
            label,
            self.resolve_arg(ref)
        )

    def compile(self):
        """Компиляция кода в последовательность инструкций."""
        print()
        print("    val:", "   var:", sep="            ")
        result = [6, len(self.data) + 2, self.NON_ZERO[0]]
        for n, v in enumerate(self.data):
            print("    ",
                  ("--                 default " if v[0] == Type.var else ""),
                  v[1],
                  " at ",
                  n, (f" [{v[2]} ref]" if v[0] == Type.static else ""),
                  sep="")
            result.append(v[1])
        print()
        result.extend(self.code)
        for n, i in enumerate(result):
            if isinstance(i, Label):
                if i.not_reassigned:
                    raise ValueError(f"{i} marked as need to be reassigned but not reassigned")
                result[n] = i.position + result[1]
        print("wait 1")
        print("\n".join([f"write {c} bank1 {n}"
                         for n, c in enumerate(result)]))
        print(f"""wait 10
jump {len(result) + 1} always 0 0""")


def cprint(chunk, text, flush=True):
    current = ""
    mode = False
    for i in text.upper():
        if i.isdigit():
            if current != "" and mode is False:
                chunk.print(current)
                current = ""
            mode = True
        else:
            if current != "" and mode is True:
                chunk.echo(chunk.store_int(int(current)))
                current = ""
            mode = False
        current += i
    if current != "" and mode is False:
        chunk.print(current)
        current = ""
    if current != "" and mode is True:
        chunk.echo(chunk.store_int(int(current)))
    if flush:
        chunk.flush()


class EmuDisplay:
    # Команды для управления дисплеем
    CLEAR = 1  # Очистка экрана
    COLOR = 2  # Установка цвета
    STROKE = 3  # Установка толщины линий
    LINE = 4  # Рисование линии
    RECT = 5  # Рисование прямоугольника
    LINE_RECT = 6  # Рисование прямоугольника только с обводкой
    POLY = 7  # Рисование многоугольника
    LINE_POLY = 8  # Рисование многоугольника только с обводкой
    TRIANGLE = 9  # Рисование треугольника
    FLUSH = 11  # Вывод всех команд на дисплей
    SHADER_MAP = 12  # Разметка сопрограммы

    # Команды для работы с видео-сопрограммами
    SHADER_EXEC = 13  # Выполнение сопрограммы
    SHADER_END = 14  # Завершить сопрограмму

    # Специальные команды
    # Начало обертки сопрограммы, позволяет устанавливать в качестве значений ссылки на память,
    # а также ограничивать количество аргументов для команды экономя размер программы
    SHADER_WRAP = 15
    SHADER_WRAP_END = -513  # Магическое число для завершения обертки сопрограммы

    NO_COMMAND = -1  # Нет команд

    DISPLAY_SIZE = 176  # Размер дисплея

    # Базовый адрес дисплея в памяти
    # Дисплей принимает 6 аргументов
    # 506 номер команды
    # 507 аргумент 1
    # 508 аргумент 2
    # 509 аргумент 3
    # 510 аргумент 4
    # 511 аргумент 5
    # 512 аргумент 6
    ADDRESS = 506

    def __init__(self, chunk: EmuChunk, use_set_4=True):
        self.chunk = chunk  # Объект EmuChunk, представляющий память команд.
        # Использовать ли оптимизированную передачу данных (по 4 параметра за раз).
        self.use_set_4 = use_set_4

    def __setitem__(self, key, value):
        """Запись значения в память для дисплея по смещению от базового адреса."""
        self.chunk[self.ADDRESS + key] = value

    def wait_for_accept(self):
        """Ожидание принятия команды дисплеем."""
        accept_label = self.chunk.label()
        self.chunk.jump_neq_const(accept_label, self.ADDRESS, -1)

    def send_command(self, command, *args, with_accept=True):
        """Отправка команды на дисплей."""
        static_args_count = 0
        for arg in args:
            if EmuChunk.is_var(arg):
                break
            static_args_count += 1
        # Если аргументов больше 3 и включен use_set_4, используем оптимизированную передачу
        if static_args_count > 3 and self.use_set_4:
            print(f"Call SET_4 with {args}")
            self.chunk.set_4(
                self.ADDRESS + 1,
                args[0],
                args[1],
                args[2],
                args[3]
            )
            args = args[4:]
        for n, arg in enumerate(args, start=1):
            self[n] = arg
        self[0] = command
        # Ожидание подтверждения выполнения
        if with_accept:
            self.wait_for_accept()

    def clear(self, r, g, b, with_accept=True):
        """Очистка экрана цветом (r, g, b)."""
        self.send_command(self.CLEAR, r, g, b, with_accept=with_accept)

    def color(self, r, g, b, a=255, with_accept=True):
        """Установка текущего цвета (r, g, b, a)."""
        self.send_command(self.COLOR, r, g, b, a, with_accept=with_accept)

    def stroke(self, size, with_accept=True):
        """Установка толщины линий."""
        self.send_command(self.STROKE, size, with_accept=with_accept)

    def line(self, x, y, x2, y2, with_accept=True):
        """Рисование линии от (x, y) до (x2, y2)."""
        self.send_command(self.LINE, x, y, x2, y2, with_accept=with_accept)

    def rect(self, x, y, w, h, with_accept=True):
        """Рисование закрашенного прямоугольника (x, y, w, h)."""
        self.send_command(self.RECT, x, y, w, h, with_accept=with_accept)

    def line_rect(self, x, y, w, h, with_accept=True):
        """Рисование контура прямоугольника (x, y, w, h)."""
        self.send_command(self.LINE_RECT, x, y, w, h, with_accept=with_accept)

    def poly(self, x, y, sides, radius, rotation, with_accept=True):
        """Рисование многоугольника."""
        self.send_command(self.POLY, x, y, sides, radius, rotation, with_accept=with_accept)

    def line_poly(self, x, y, sides, radius, rotation, with_accept=True):
        """Рисование контура многоугольника."""
        self.send_command(self.LINE_POLY, x, y, sides, radius, rotation, with_accept=with_accept)

    def triangle(self, x, y, x2, y2, x3, y3, with_accept=True):
        """Рисование треугольника с вершинами (x, y), (x2, y2), (x3, y3)."""
        self.send_command(self.TRIANGLE, x, y, x2, y2, x3, y3, with_accept=with_accept)

    def flush(self, with_accept=True):
        """Отправка всех команд на дисплей."""
        self.send_command(self.FLUSH, with_accept=with_accept)

    def shader_map(self, index, start_addr, with_accept=True):
        """Привязка сопрограммы к индексу."""
        self.send_command(self.SHADER_MAP, index, start_addr, with_accept=with_accept)
        return index

    def shader_exec(self, index, with_accept=True):
        """Выполнение сопрограммы по индексу."""
        self.send_command(self.SHADER_EXEC, index, with_accept=with_accept)

    def alloc_shader(self, *args):
        """Определение сопрограммы в памяти"""
        addr = self.chunk.label()
        for arg in args:
            if EmuChunk.is_var(arg):
                self.chunk.append(-arg[0])
                continue
            self.chunk.append(arg)
        addr.position += 1
        return addr


def level_up(func: Callable):
    """Повышает уровень кода, по отступам, код остается говном даже с использованием данной функции"""
    func()
