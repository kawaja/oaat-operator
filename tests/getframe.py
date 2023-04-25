from oaatoperator.utility import my_details


def depth1(v, *a, **k):
    print(my_details())
    depth2(v)


def depth2(w, **k):
    print(my_details())
    print(my_details(1))


depth1(5, 6, 7, a=1, b=2, c='x')
