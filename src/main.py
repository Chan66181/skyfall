import pyfiglet
from termcolor import cprint




def main(): 
    ascii_banner = pyfiglet.figlet_format("Let the sky fall!", font="slant")
    border = "-" * 76
    cprint(border, "cyan")
    cprint(ascii_banner, "cyan")
    cprint(border, "cyan")
    
    
if __name__ == "__main__":
    main()