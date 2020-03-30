"""
Tools for making Vuforia queries.
"""

class MatchingTargetsWithProcessingStatus(Exception):
    pass

class ActiveMatchingTargetsDeleteProcessing(Exception):
    pass

def _images_match(image: io.BytesIO, another_image: io.BytesIO) -> bool:
    """
    Given two images, return whether they are matching.

    In the real Vuforia, this matching is fuzzy.
    For now, we check exact byte matching.

    See https://github.com/adamtheturtle/vws-python-mock/issues/3 for changing
    that.
    """
    return bool(image.getvalue() == another_image.getvalue())


def _get_query_matches(image: io.BytesIO, database: VuforiaDatabase):
    """
    Given an image and a database, return the matches for a query.
    """
    pass

def _get_query_match_result_data(

)
