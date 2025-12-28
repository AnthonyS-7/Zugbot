import logging

# Alignments Enum Start
class Alignment:
    def __init__(self, alignment: int) -> None:
        self.alignment = alignment
        pass

TOWN = Alignment(0)
MAFIA = Alignment(1)
# Alignments Enum End

# Action Submission Enum Start
IN_THREAD = 0
IN_PM = 1
# Action Submission Enum End (for factional chats, IN_PM submission will eventually allow Discord submission)

# Action Types Start
INVESTIGATIVE = "investigative"
COMMUNICATIVE = "communicative"
KILLING = "killing"
MANIPULATIVE = "manipulative"
PROTECTIVE = "protective"

FALSE_ACTION = "false_action" # Used for abilities which are not actually actions, such as requesting votecounts
# Action Types End

LOGGER = logging.Logger(name="latest.log")
DEBUG = logging.DEBUG
ERROR = logging.ERROR