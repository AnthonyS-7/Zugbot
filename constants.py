# Alignments Enum Start
class Alignment:
    def __init__(self, alignment: int) -> None:
        self.alignment = alignment
        pass

    def __eq__(self, other):
        if type(other) != Alignment:
            return False
        return self.alignment == other.alignment
    
    def string_rep(self):
        if self == TOWN:
            return 'Town'
        if self == MAFIA:
            return 'Mafia'
        return 'ERROR (this shouldn\'t ever happen)'

TOWN = Alignment(0)
MAFIA = Alignment(1)
# Alignments Enum End

# Action Submission Enum Start
IN_THREAD = 0
IN_PM = 1
IN_WOLFCHAT = 2
# Action Submission Enum End (for factional chats, IN_PM submission will eventually allow Discord submission)

# Action Types Start
INVESTIGATIVE = "investigative"
COMMUNICATIVE = "communicative"
KILLING = "killing"
MANIPULATIVE = "manipulative"
PROTECTIVE = "protective"
ACTION_TYPE_OTHER = "other"

FALSE_ACTION = "false_action" # Used for abilities which are not actually actions, such as requesting votecounts
# Action Types End

SETUP_FOLDER = "setups" # not in config because it should never be changed.
SETUP_FILE_NAME = "setup_definition" # excludes the .py intentionally
FLIPS_FOLDER_NAME = "flips"