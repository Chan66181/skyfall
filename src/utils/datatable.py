class DataTable:
    def __init__(self, headers):
        self.headers = list(headers)
        self.rows = []

    def add_row(self, row):
        if len(row) > len(self.headers):
            raise ValueError("Too many values in row.")
        # Fill missing columns with None
        row += [None] * (len(self.headers) - len(row))
        self.rows.append(row)

    def add_column(self, column_name, default=None):
        if column_name in self.headers:
            raise ValueError(f"Column '{column_name}' already exists.")
        self.headers.append(column_name)
        for row in self.rows:
            row.append(default)

    def get_row(self, index) -> dict:
        if not isinstance(index, int):
            raise TypeError("Row index must be an integer.")
        if index < 0 or index >= len(self.rows):
            raise IndexError(f"Row index {index} is out of range (0–{len(self.rows) - 1}).")
        return dict(zip(self.headers, self.rows[index]))
    
    def show_table_and_select(self, title:str=None) -> int:
        self.print_table(title=title)
        while True:
            choice = input("\nSelect a row by number: ").strip()
            if not choice.isdigit():
                print("[!] Please enter a valid number.")
                continue

            idx = int(choice)
            if 1 <= idx <= len(self.rows):
                return self.get_row(idx - 1)
            else:
                print(f"[!] Out of range (1–{len(self.rows)}).")


    def print_table(self, title=None):
        if title:
            print(f"\n{title}\n")

        # Calculate column widths
        col_widths = [len(h) for h in self.headers]
        for row in self.rows:
            for i, item in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(item)) if item is not None else 4)

        # Row format string
        row_fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_widths) + " |"

        # Border line
        border = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

        # Print table with full frame
        print(border)
        print(row_fmt.format(*self.headers))
        print(border)
        for row in self.rows:
            display_row = [str(col) if col is not None else "None" for col in row]
            print(row_fmt.format(*display_row))
        print(border)

