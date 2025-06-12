Need:

- way to determine what abilities can be used together (likely give each ability a vector of "cost" to use, and require that each entry of the sum of all abilities used is less than some maximum.)
- way to log what was used, and make trackers/watchers work
- way to indicate what is standard and well-behaved
- way to do NAR
- standard modifiers

The following is a list of all Standard Zugbot mech. (...once this is implemented.)

For Standard roles, the following is true:
- Methods of the Player class are never overridden / swapped for methods that do different things
- 


Many of the things that are usually called "modifiers" are instead known as Passives within Zugbot. For example, Miller, Godfather, and Bulletproof are all passives. Passive abilities are ones that only change the methods provided by the Player interface (such as get_alignment), while Actives have actual Ability objects.

Zugbot also has Modifiers - these are a set of parameters that are passed by any Abilities to player methods (such as get_alignment and receive_protection). For example, suppose a town role investigates a player, learning their alignment, and also protects that player. Suppose the invest_power of this role is 1, and the protection_level is 2. This role calls target_player.get_alignment(invest_power=invest_power), but it happens that the target is a miller of invest_power=2, so it is reported that this player is Mafia. The target has a normal receive_protection method, so their protection is increased by 2, since protection_level=2.

As seen in the example above, both Abilities and Passives can have Modifiers.

# Standard Abilities:
- Visitor (Visits a player, no other effects)
- Non-visiting Alignment Cop
- Non-visiting Doctor
- Non-visiting Role Cop
- Non-visiting Vigilante

# Standard Passive List
- get_alignment:
  - Godfather: Appears as town to get_alignment().
  - Miller: Appears as mafia to get_alignment().
- take_damage:
  - Bulletproof: take_damage() does nothing.
- receive_protection:
  - Macho: 

# Standard Role Modifiers:
- invest_power: float > 0. Standard = 1.
  - invest_power determines whether investigative results are true. Note that anything that accesses a player's alignment through get_alignment is an investigation - so, if Loyal/Disloyal are supposed to pierce through Millers/Godfathers, the Miller/Godfather invest_power should be lower than that of the action.
- protection_level: float > 0. Standard = 1.
  - protection_level determines how much protection is provided by protective actions.
- protection_multiplier: float >= 0.
- attack_piercing: float. Standard = 1 for attacks, 0 
  - 