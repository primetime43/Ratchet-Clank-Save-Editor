# Ratchet Clank Save Editor
Ratchet &amp; Clank Save Editor for PS3 OFW

I originally made this back in 2014, I've decided to go back and rewrite the program some to improve it a bit.

Here is a ratchet & clank save editor for all the Ratchet and Clanks (Ratchet & Clank™: Nexus, Ratchet & Clank® Future: Quest for Booty™, Ratchet & Clank Tools of Destruction, Ratchet & Clank, Ratchet & Clank: Going Commando, Ratchet & Clank: Up Your Arsenal, Ratchet: Deadlocked, Ratchet & Clank Future: Tools of Destruction and Ratchet & Clank Future: Quest for Booty). 
I made this for fun for myself at first, but then figured that maybe others want to have a little advantage in the game also, so I decided to release it for ya.


```
//Ratchet & Clank 1 (original)
0x24 - Number of bolts (4 bytes)
0x15b - Ammo for Blaster (Max value 200)(C (If you go above C8, the max, the game with reset to new game) 
(All ammo is one byte) //That goes for all the ammo
0x153 - Visibomb Ammo  (Max value 20) (14)
0x14b - Devastator Ammo (Max value 20) (14)
0x16f - Gold Glove of Doom Ammo (Max value 10) (0A)
0x17b - R.Y.N.O Ammo (Max value 50) (32)
0x17f - Drone Ammo (Max value 10) (0A)
0x147 - Bomb Glove Ammo (Max value 40) (2
0x15f - Pyrociter Ammo (Max value 240) (F0)
0x163 - Mine Glove Ammo (Max value 50) (32)
0x16B - Telsa Claw Ammo (Max value 240) (F0)
0x183 - Decoy Glove Ammo (Max value 20) (14)

//Ratchet & Clank 2: Going Commando
0x24 - Number of bolts (4 bytes)
0x28 - Number of Raritanium (4 bytes)

//Ratchet & Clank: Up Your Arsenal
0x24 - Number of bolts (4 bytes)

//Ratchet & Clank Quest For Booty
0x274 - Number of bolts (4 bytes)
```
