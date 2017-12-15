from abc import ABC, abstractmethod

import pandas as pd
from collections import defaultdict
from pandas.io.formats.terminal import get_terminal_size


class BaseWriter(ABC):
    @abstractmethod
    def write_data_frame(self, data_frame, sheet_name, index_label):
        raise NotImplemented

    def save(self):
        pass


class ExcelWriter(BaseWriter):
    spacing = 2

    def __init__(self, ouput_path):
        self.writer = pd.ExcelWriter(ouput_path, engine='xlsxwriter')
        self.sheet_positions = defaultdict(int)

    def write_data_frame(self, data_frame, sheet_name, index_label):
        sheet_position = self.sheet_positions[sheet_name]
        data_frame.to_excel(
            self.writer, sheet_name,
            index_label=index_label, startrow=sheet_position
        )
        self.sheet_positions[sheet_name] = sheet_position + len(data_frame) + self.spacing

    def save(self):
        self.writer.save()


class ConsoleWriter(BaseWriter):
    def __init__(self):
        self.sheets = set()
        pd.set_option('display.width', get_terminal_size().columns)

    def write_data_frame(self, data_frame, sheet_name, index_label):
        if sheet_name not in self.sheets:
            header1 = '=' * 20
            print('\n%s %s %s' % (header1, sheet_name, header1))
            self.sheets.add(sheet_name)
        if index_label:
            header2 = '-' * 10
            print('\n%s %s %s' % (header2, index_label, header2))
        print()
        print(data_frame)
