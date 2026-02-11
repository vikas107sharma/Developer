from time import time, sleep
import copy


class Clone:
    def clone(self):
        # Deep copy prevents shared mutable references
        return copy.deepcopy(self)


class NPC(Clone):
    def __init__(self, name, health, attack, defence, inventory, skills):
        print("Creating NPC...")
        self._name = name
        self._health = health
        sleep(1)
        self._attack = attack
        self._defence = defence
        sleep(1)
        self._inventory = inventory
        self._skills = skills
        sleep(1)
        print("NPC created !!")
    
    

    def __repr__(self):
        return (
            f"NPC(name={self.name}, health={self.health}, "
            f"attack={self.attack}, defence={self.defence}, "
            f"inventory={self.inventory}, skills={self.skills})"
        )


start = time()

# Expensive creation
base_npc = NPC(
    name="Orc Warrior",
    health=200,
    attack=40,
    defence=25,
    inventory=["Axe", "Armor"],
    skills={"rage": 5, "smash": 3}
)

print("Creation time:", round(time() - start, 2), "seconds\n")


# Fast cloning
clone_start = time()
npc1 = base_npc.clone()
npc1.name = "Orc Warrior A"
npc1.inventory.append("Health Potion")

print("Clone time:", round(time() - clone_start, 4), "seconds\n")

print("Base NPC:", base_npc)
print("Cloned NPC:", npc1)
