"""
Post class from Terminal of Lies, modified for Zugbot.
"""

import re
import datetime

quoteMatcher = re.compile(r"(\[quote.*?\])(.*?)(\[/quote\])", re.IGNORECASE | re.DOTALL)


@staticmethod
def removeQuotes(post_content: str) -> str:
    """
    Given a string, removes all BBCode quotes in it.

    TODO: make this not have edge case bugs. Or maybe don't, because it's likely that all 
    edge cases just make it work even when the user messed up quote tags (and in these cases,
    the vote wasn't intentional anyway).
    """
    post_has_quotes = True
    while(post_has_quotes):
        post_content, post_has_quotes = removeOneQuote(post_content)
    return post_content

def removeOneQuote(post_content: str) -> list:
    """
    Returns a list of the form [post_with_quote_removed, True if post_content was changed else False]
    """
    currentMatch = quoteMatcher.search(post_content)
    if currentMatch is None:
        return [post_content, False]

    currentIndex = 0
    while currentMatch != None:
        start, end = currentMatch.start(1) + currentIndex, currentMatch.end(3) + currentIndex
        currentIndex += currentMatch.end(1)
        currentMatch = quoteMatcher.search(post_content[currentIndex:])
    return [post_content[0:start] + post_content[end:], True]



class Post:
    def __init__(self, poster: str, timestamp: str, postNumber, content: str, topicNumber: str):
        self.poster = poster
        self.timestamp = timestamp
        try:
            self.datetime_timestamp = datetime.datetime.strptime(self.timestamp, "%Y-%m-%d %H:%M:%S %Z")
        except ValueError as e:
            print(f"Exception of type {type(e)} when parsing with raw text format - trying next format.")
            period_index = self.timestamp.find(".")
            self.datetime_timestamp = datetime.datetime.strptime(self.timestamp[0:period_index], "%Y-%m-%dT%H:%M:%S")
        self.postNumber = str(postNumber)
        self.content_with_quotes = content
        self.content = removeQuotes(content)
        self.topicNumber = topicNumber
        # self.vote = self.findVote()
        # self.cleanVotes()

    def quoteString(self):
        totalString = f'[quote="{self.poster}, post: {self.postNumber}, topic: {self.topicNumber}"]'
        totalString += "\n" + self.content + "\n"
        totalString += "[/quote]" + "\n"
        return totalString

    def displayString(self):
        return self.poster + ", " + self.timestamp + ", " + self.postNumber + "\n" + self.content

    # #returns True if the post contains an unvote
    # def findUnvote(self):
    #     unvoteTester = re.compile(r"\[unvote\].*\[/unvote\]", re.IGNORECASE)
    #     return unvoteTester.search(removeQuotes(self.content))
    
    # #given the content of a post, returns the substring that is a valid vote, or returns
    # #None if no such substring exists
    # def getVoteString(self):
    #     voteFull = re.compile(r"\[vote\].*?\[/vote\]", re.IGNORECASE)
    #     voteFullMini = re.compile(r"\[v\].*?\[/v\]", re.IGNORECASE)
    #     fullMatch = voteFull.search(removeQuotes(self.content))
    #     miniMatch = voteFullMini.search(removeQuotes(self.content))
    #     actualVote = None
    #     if fullMatch != None:
    #         actualVote = fullMatch.group(0)
    #     elif miniMatch != None:
    #         actualVote = miniMatch.group(0)
    #     else:
    #         return None
    #     actualVote = actualVote[actualVote.find("]") + 1:len(actualVote)]
    #     actualVote = actualVote[0:actualVote.find("[")]
    #     return actualVote
    
    # #returns the (un)vote in the post (ie the voted player); or None if no such vote exists
    # def findVote(self):
    #     unvote = self.findUnvote()
    #     vote = self.getVoteString()
    #     if unvote != None:
    #         return "unvote"
    #     return vote

    # #removes spaces and newlines from vote
    # def cleanVotes(self):
    #     if self.vote != None:
    #         self.vote = self.vote.replace(" ", "")
    #         self.vote = self.vote.replace(r"\n", "")

    def contains(self, string: str, ignoreCase=False) -> bool:
        if ignoreCase:
            return self.content.lower().find(string.lower()) != -1
        return self.content.find(string) != -1
    
    def stringCount(self, string: str, ignoreCase=False) -> int:
        """
        Returns the number of times the parameter occurs in the post.
        """
        if ignoreCase:
            return self.content.lower().count(string.lower())
        return self.content.count(string)
