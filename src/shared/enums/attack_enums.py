from enum import Enum, auto

class Manufacturer(Enum):
    PARROT = "Parrot"
    DJI = "DJI"
    # add more as needed

class Model(Enum):
    # ParrotModel
    PARROT_AR2 = "AR 2.0"
    PARROT_BEBOP = "Bebop"
    # DJi Model
    DJI_PHANTOM = "Phantom"
    DJI_MAVIC = "Mavic"
    # extend here

class AttackType(Enum):
    DEAUTH = auto()
    DOS = auto()
    CONTROL_HIJACK = auto()
    VIDEO_HIJACK = auto()
    TELNET_SHELL = auto()
    ARP_SPOOF = auto()
    DISCONNECT_CONTROLLER = auto()
    CONNECT_TO_WIFI = auto()
