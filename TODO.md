Zugbot 0.1 - mountainous - complete; needs testing

Zugbot 1.0 - Abilities! Will consider Zugbot to be in 1.0 when it runs a longform game.

TO TEST:

- topic closing timer & does it still work with no start time specified

BEFORE RUNNING SETUP:

- proxying instant actions should be a thing (if private instant actions exist)
- Make it not count votes past the EOD time but before thread lock

Future plans:

- Implement Natural action resolution, instead of hardcoded priorities (this will be difficult)
- Fix the fact there's an invalid_flip.txt and an INVALID_FLIP constant, used in different places and not even the same string
- Make canon of "standard" roles and parameters that can be used to modify the effects of those roles. Currently, roles tend to be coupled to eachother, and this problem only gets worse when roles are more complicated. By making standard actions, that have many parameters for things to tie into (ex: Godfather with a falsifiable parameter to bypass it), and documentation that explains this, then all roles can be coupled to a documented standard, which is much easier when trying to mix roles from different games. 
- Make discord submission work for more than nightkills
- Give it a website to be run by anyone from

KNOWN BUGS:

- If two actions are submitted in different topics in the same second, they may end up out of order. (unlikely to actually cause issues)
- When posting a votecount, if someone votes between the time the VC plugin is queried and the VC is posted,
  their vote will be erased

Probable bugs: 

