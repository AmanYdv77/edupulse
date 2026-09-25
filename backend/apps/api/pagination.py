from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination for API list endpoints.
    Default page size is 25, client can request up to max 100.
    """
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
