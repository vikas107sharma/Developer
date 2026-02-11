from time import time, sleep
import copy


class Clone:
    def clone(self):
        return copy.deepcopy(self)


class NPC(Clone):
    def __init__(self, name, health, attack, defence, inventory, skills):
        print("Creating NPC...")

        self.__name = name
        self.__health = health
        sleep(1)

        self.__attack = attack
        self.__defence = defence
        sleep(1)

        # Copy to avoid external reference injection
        self.__inventory = list(inventory)
        self.__skills = dict(skills)
        sleep(1)

        print("NPC created !!")

    # -------------------
    # Getters
    # -------------------

    @property               # @property turns a method into an attribute-like getter.
    def name(self):
        return self.__name

    @property
    def health(self):
        return self.__health

    @property
    def attack(self):
        return self.__attack

    @property
    def defence(self):
        return self.__defence

    @property
    def inventory(self):
        return list(self.__inventory)  # return copy (read-only safety)

    @property
    def skills(self):
        return dict(self.__skills)  # return copy

    # -------------------
    # Setters (Validated)
    # -------------------

    @name.setter                    # setter works like:  npc1.name = "Orc Warrior A"
    def name(self, value):          # If this decorator is not there:   npc1.set_name("Orc Warrior A")
        if not value:
            raise ValueError("Name cannot be empty")
        self.__name = value

    @health.setter
    def health(self, value):
        if value < 0:
            raise ValueError("Health cannot be negative")
        self.__health = value

    @attack.setter
    def attack(self, value):
        if value < 0:
            raise ValueError("Attack cannot be negative")
        self.__attack = value

    @defence.setter
    def defence(self, value):
        if value < 0:
            raise ValueError("Defence cannot be negative")
        self.__defence = value

    # -------------------
    # Controlled Mutations
    # -------------------

    def add_item(self, item):
        self.__inventory.append(item)

    def upgrade_skill(self, skill, level):
        if level < 0:
            raise ValueError("Skill level cannot be negative")
        self.__skills[skill] = level

    def __repr__(self):
        return (
            f"NPC(name={self.__name}, health={self.__health}, "
            f"attack={self.__attack}, defence={self.__defence}, "
            f"inventory={self.__inventory}, skills={self.__skills})"
        )


# -------------------
# Performance Demo
# -------------------

start = time()

base_npc = NPC(
    name="Orc Warrior",
    health=200,
    attack=40,
    defence=25,
    inventory=["Axe", "Armor"],
    skills={"rage": 5, "smash": 3}
)

print("Creation time:", round(time() - start, 2), "seconds\n")


clone_start = time()

npc1 = base_npc.clone()
npc1.name = "Orc Warrior A"
npc1.add_item("Health Potion")
npc1.upgrade_skill("rage", 7)

print("Clone time:", round(time() - clone_start, 4), "seconds\n")

print("Base NPC:", base_npc)
print("Cloned NPC:", npc1)
