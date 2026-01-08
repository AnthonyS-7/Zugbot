# Necessary Capabilities

- Way to determine what abilities can be used together (likely give each ability a vector of "cost" to use, and require that each entry of the sum of all abilities used is less than some maximum. this vector should actually be a dictionary, for more meaningful indexing)
  - Doing this through AbilityRestrictions.
- Way to log what was used, and make trackers/watchers work
   - Going to make the action processor record visits and action types, and store these logs in the gamestate.
- Way to indicate what is standard and well-behaved
   - Going to add a boolean variable to Ability
- Way to do NAR
   - Will be handled by the action processor, and will be restricted to only when there are standard/well-behaved abilites in play.
   - Likely toggleable in the config.
- Standard modifiers
  - Doing this through AbilityModifiers (on the Ability side) and Passives (on the Player side)

The following is a list of all Standard Zugbot mech. (...once this is implemented.)

# Standard Passives
Standard Passives are all given through fields in the Player object. A list of Standard Passives:
  - voting_power: int, default 1.
  - voting_power_is_public: bool, default True.
    - This determines whether their voting_power shows up on VCs, or appears as a single vote.
  - invest_alignment: Alignment | None, default None.
    - This is the (possibly false) alignment the player can investigate as.
  - invest_resistance: float, default 1.
    - If the invest_power of the investigation is less than or equal to invest_resistance, the invest will receive invest_alignment (or other possibly false results). Otherwise, the invest will receive true results.
  - protection_multiplier: float >= 0, default 1.
    - Incoming protection is multiplied by this. Can be used to implement Macho, among other things.
  - damage_multiplier: float >= 0, default 1
    - Incoming damage is multiplied by this. Can be used to implement Bulletproof, among other things.

There are additionally some player fields that correspond to other things:
  - Player fields that correspond to redirection currently active on this player:
    - redirect_player: Player | None, default None
    - redirection_strength
    - focus_increase_on_redirection
  - Player fields that correspond to other parts of the Player state (generally, these can be mutated throughout the game even if that player's role doesn't change):
    - protection: float, default 0
    - willpower: float, default 0
    - health: float >= 0, default 1 ('full' health), 0 is dead

Zugbot also has Modifiers - these are a set of parameters that are passed by any Abilities to player methods (such as get_alignment and receive_protection). For example, suppose a town role investigates a player, learning their alignment, and also protects that player. Suppose the invest_power of this role is 1, and the protection_level is 2. This role calls target_player.get_alignment(invest_power=invest_power), but it happens that the target is a miller of invest_power=2, so it is reported that this player is Mafia. The target has a normal receive_protection method, so their protection is increased by 2, since protection_level=2.

As seen in the example above, both Abilities and Passives can have Modifiers.

# Standard Abilities:
- Visitor (Visits a player, no other effects)
- Alignment Cop
- Doctor
- Vigilante
- add more...

# Standard Role Modifiers:
- invest_power: float > 0. Standard = 1.
  - invest_power determines whether investigative results are true. Note that anything that accesses a player's alignment through get_alignment is an investigation - so, if Loyal/Disloyal are supposed to pierce through Millers/Godfathers, the Miller/Godfather invest_power should be lower than that of the action.
- protection_level: float > 0. Standard = 1.
  - protection_level determines how much protection is provided by protective actions.
