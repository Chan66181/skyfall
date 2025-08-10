from enum import Enum, auto

class Manufacturer(Enum):
    PARROT = "Parrot"
    DJI = "DJI"
    # add more as needed

class ParrotModel(Enum):
    AR2 = "AR 2.0"
    BEBOP = "Bebop"
    # extend here

class DjiModel(Enum):
    PHANTOM = "Phantom"
    MAVIC = "Mavic"
    # extend here

class AttackType(Enum):
    DEAUTH = auto()
    DDOS = auto()
    CONTROL_HIJACK = auto()
    VIDEO_HIJACK = auto()
    TELNET_SHELL = auto()
    ARP_SPOOF = auto()
    DISCONNECT_CONTROLLER = auto()
    CONNECT_TO_WIFI = auto()
