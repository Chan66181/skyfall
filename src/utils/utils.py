import os

def load_shell_binaries() -> list[str]:
    """
    Loads common shell binaries from typical PATH locations.
    This is a simplified example. A more robust version might parse $PATH
    and check for executable files in each directory.
    """
    common_paths = ['/usr/local/bin', '/usr/bin', '/bin', '/sbin', '/usr/sbin']
    binaries = set()
    for path in common_paths:
        if os.path.isdir(path):
            try:
                for item in os.listdir(path):
                    full_path = os.path.join(path, item)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        binaries.add(item)
            except PermissionError:
                # Handle cases where the script might not have permission to list a directory
                pass
    # Add some very common built-in commands that might not be in PATH directories
    binaries.update(["ls", "cd", "pwd", "echo", "cat", "grep", "mv", "cp", "rm", "mkdir", "rmdir", "which", "man"])
    return sorted(list(binaries))