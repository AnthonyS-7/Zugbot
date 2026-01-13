# BEFORE RUNNING SETUPS:

- Proxying instant actions should be a thing (if private instant actions exist)
- Make it not count votes past the EOD time but before thread lock
   - Particularly problematic if the bot doesn't lock the thread in time for whatever reason (ex: connection issues)

# Future plans:

- Fix the fact there's an invalid_flip.txt and an INVALID_FLIP constant, used in different places and not even the same string
- Finish roles refactoring/improvements (detailed more in abilities_standard.py) 
   - Includes implementing Natural Action Resolution
- Make discord submission work for more than nightkills
- Give it a website to be run by anyone from

# KNOWN BUGS:

- If two actions are submitted in different topics in the same second, they may end up out of order. (unlikely to actually cause issues)


#  TODO for turbo implementation
- popcorn
- cop9
- godfather9
- ita10
- bomb10

roles required:
- popcorn roles
- inventor who gives a bomb
- miller / godfather
- PR killer

other reqs:
- ITAs
- The setups themselves

Things almost finished:
- Cop (still needs n0 peek option)

Things finished but needs testing:
- Vigilante
- Innocent child
- joat (1x cop, 1x doctor, 1x vig)
   - multitask restrictions included
- inventor who gives a desperado item
- Wolfchat (and factional kill submission) on the forum
- turbos.py updates
- Shot restrictions (i.e. 1-shot)
- cycle restrictions
- inno7, inno4
- desp8
- joat10



Note on Inventors: The inventor roles for these turbos will simply grant the target player an ability. Eventually, Zugbot will have an item system, but for these particular roles it is overkill. Because I am implementing inventors in this way (instead of in the more generalizable way of giving an item)