from abc import ABC, abstractmethod

# Target interface (what system expects)
class DamageSystem(ABC):
    @abstractmethod
    def deal_damage(self, target, amount):
        pass


# Legacy Systems (Incompatible)
class FireDamageSystem:
    def burn(self, enemy, intensity):
        print(f"🔥 Burning {enemy} with {intensity} fire damage")


class IceDamageSystem:
    def freeze(self, enemy, power):
        print(f"❄️ Freezing {enemy} with {power} ice damage")


# -------------------------------
# Object Adapter (Composition)
# -------------------------------

class FireAdapter(DamageSystem):
    def __init__(self, fire_system: FireDamageSystem):
        self.fire_system = fire_system   # wrapped object

    def deal_damage(self, target, amount):
        self.fire_system.burn(target, amount)


class IceAdapter(DamageSystem):
    def __init__(self, ice_system: IceDamageSystem):
        self.ice_system = ice_system

    def deal_damage(self, target, amount):
        self.ice_system.freeze(target, amount)


# ----------------------
# Usage
# ----------------------

legacy_fire_system = FireDamageSystem()
fire_adapter = FireAdapter(legacy_fire_system)
fire_adapter.deal_damage("Orc", 50)


legacy_ice_system = IceDamageSystem()
ice_adapter = IceAdapter(legacy_ice_system)
ice_adapter.deal_damage("Dragon", 100)