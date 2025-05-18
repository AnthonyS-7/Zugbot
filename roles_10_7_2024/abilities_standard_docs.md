Need:

- way to determine what abilities can be used together (likely give each ability a vector of "cost" to use, and require that each entry of the sum of all abilities used is less than some maximum.)
- way to log what was used, and make trackers/watchers work
- way to indicate what is standard and well-behaved
- way to do NAR
- standard modifiers


# Standard Modifier List
- Modifiers on Players:
  - Godfather: Appears as town to get_alignment(). Overridden by parameter true_invest=True.
  - Miller: Appears as mafia to get_alignment().
  Overridden by parameter true_invest=True.
  - Bulletproof: take_damage() does nothing. Overridden by strongman=True.
  - 
- Modifiers on Actions:
  - 