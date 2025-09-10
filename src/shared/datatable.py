from typing import Optional, List, Dict, Any, Union

class DataTable:
    def __init__(self, headers: List[str]):
        self.headers = list(headers)
        self.rows = []

    def add_row(self, row_data: List[Any]):
        if len(row_data) > len(self.headers):
            raise ValueError(f"Too many values in row. Expected {len(self.headers)}, got {len(row_data)}.")
        
        padded_row = list(row_data) + [None] * (len(self.headers) - len(row_data))
        self.rows.append(padded_row)

    def add_column(self, column_name: str, default: Optional[Union[str, int]] = None):
        if column_name in self.headers:
            raise ValueError(f"Column '{column_name}' already exists.")
        
        self.headers.append(column_name)
        for row in self.rows:
            row.append(default)

    def get_row(self, index: int) -> Dict[str, Any]:
        if not isinstance(index, int):
            raise TypeError("Row index must be an integer.")
        if index < 0 or index >= len(self.rows):
            raise IndexError(f"Row index {index} is out of range (0–{len(self.rows) - 1}).")
        return dict(zip(self.headers, self.rows[index]))
    
    def get_row_count(self) -> int:
        return len(self.rows)
    
    def get_all_rows_as_dicts(self) -> List[Dict[str, Any]]:
        all_dicts = []
        for row_list in self.rows:
            all_dicts.append(dict(zip(self.headers, row_list)))
        return all_dicts

    def update_row_by_sno(self, s_no: int, new_data: Dict[str, Any]):
        if "S.No" not in self.headers:
            print("[!] Warning: 'S.No' column not found in table headers. Cannot update by S.No.")
            return

        s_no_idx = self.headers.index("S.No")

        found = False
        for row_list in self.rows:
            if row_list[s_no_idx] == s_no:
                for col_name, new_value in new_data.items():
                    try:
                        col_idx = self.headers.index(col_name)
                        row_list[col_idx] = new_value
                    except ValueError:
                        print(f"[!] Warning: Column '{col_name}' not found in headers for update.")
                found = True
                break
        if not found:
            print(f"[!] Warning: Row with S.No {s_no} not found for update.")

    def show_table_and_select(self, title: Optional[str] = None, selection_message = "\nSelect a row by S.No (or 'q' to quit): ") -> Optional[Dict[str, Any]]:
        self.print_table(title=title)
        if not self.rows:
            print("No rows to select from.")
            return None

        while True:
            choice = input(selection_message).strip().lower()
            if choice == 'q':
                print("Selection cancelled.")
                return None
            if not choice.isdigit():
                print("[!] Please enter a valid number or 'q'.")
                continue

            selected_s_no = int(choice)
            
            try:
                s_no_col_idx = self.headers.index("S.No")
            except ValueError:
                print("[!] Error: 'S.No' column not found in table headers. Cannot select by S.No.")
                return None

            found_row_data = None
            for row_list in self.rows:
                if row_list[s_no_col_idx] == selected_s_no:
                    found_row_data = row_list
                    break

            if found_row_data:
                return dict(zip(self.headers, found_row_data))
            else:
                print(f"[!] S.No {selected_s_no} is out of range or does not exist. Please enter a valid S.No from the table.")

    def print_table(self, title: Optional[str] = None):
        if title:
            print(f"\n{title}\n")

        if not self.headers:
            print("[!] Table has no headers to display.")
            return
        
        col_widths = [len(h) for h in self.headers]
        for row in self.rows:
            for i, item in enumerate(row):
                cell_content = str(item) if item is not None else "None"
                col_widths[i] = max(col_widths[i], len(cell_content))

        row_fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_widths) + " |"
        border = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

        print(border)
        print(row_fmt.format(*self.headers))
        print(border)
        if not self.rows:
            print(f"| {' ' * (len(border) - 4)} |")
            print(border)
        else:
            for row in self.rows:
                display_row = [str(col) if col is not None else "None" for col in row]
                print(row_fmt.format(*display_row))
            print(border)