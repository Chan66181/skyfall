import cmd
import shlex
import subprocess
from .utils import *

class SkyFallConsole(cmd.Cmd):
    intro = "Welcome to Skyfall — The Drone Killer Console. Type ? or 'help' to see commands.\n"
    prompt = "skyfall> "
    
    def __init__(self, completekey = "tab", stdin = None, stdout = None):
        super().__init__(completekey, stdin, stdout)
        self.shell_binaries = load_shell_binaries()

    def do_scan(self, arg):
        args = shlex.split(arg)
        if "--wifi" in args:
            print("Scanning wifi frequencies....")
 
    def complete_scan(self, text, state):
        return super().complete(text, state)

    
    def do_quit(self, line):
        """Exit the CLI."""
        return True 
    
    def default(self, line):
        """Fallback: Execute unknown commands as shell commands"""
        try:
            subprocess.run(line, shell=True)
        except Exception as e:
            print(f"Shell command failed: {e}")
                        
    def completenames(self, text, *ignored):
        dotext = 'do_'+text
        op = [a[3:] for a in self.get_names() if a.startswith(dotext)]
        op += [a for a in self.shell_binaries if a.startswith(text)]
        return op
    
    

    # ----- record and playback -----
    # def do_record(self, arg):
    #     'Save future commands to filename:  RECORD rose.cmd'
    #     self.file = open(arg, 'w')
        
    # def do_playback(self, arg):
    #     'Playback commands from a file:  PLAYBACK rose.cmd'
    #     self.close()
    #     with open(arg) as f:
    #         self.cmdqueue.extend(f.read().splitlines())
    
    # def close(self):
    #     if self.file:
    #         self.file.close()
    #         self.file = None