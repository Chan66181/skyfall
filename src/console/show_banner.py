import pyfiglet
from termcolor import cprint

def show_banner():
    ascii_banner = pyfiglet.figlet_format("Let the drone fall!", font="slant")
    border = "-" * 76
    cprint(border, "cyan")
    cprint(ascii_banner, "cyan")
    cprint(border, "cyan")