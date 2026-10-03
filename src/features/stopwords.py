"""Stopwords used ONLY to separate content words for diversity/novelty measures. They are never removed from the
transcript itself, and negations/contrast words (not, never, but, however, although) are kept in the text."""
STOPWORDS = frozenset(
    """a an the and or if then so of to in on at by for with from as is are was were be been being it its this that these those
    i you he she we they me my your our their them his her do does did done have has had will would can could should may might just
    very really also about into over than too out up down all any more most some such what which who when where why how there here
    get got let lets like one two im ive youre dont thats yeah okay um uh basically actually literally""".split()
)
