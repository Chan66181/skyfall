from console import SkyFallConsole, show_banner


    
if __name__ == "__main__":
    try:
        show_banner()
        SkyFallConsole().cmdloop()
    except KeyboardInterrupt:
        print("\n[!] Ctrl+C detected. Exiting Skyfall.")