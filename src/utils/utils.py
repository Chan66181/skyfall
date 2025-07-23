import os

def load_shell_binaries() -> list:
        """Load all shell commands once from $PATH"""
        binaries = set()
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            if os.path.isdir(path_dir):
                try:
                    for filename in os.listdir(path_dir):
                        binaries.add(filename)
                except PermissionError:
                    continue
        return sorted(binaries)