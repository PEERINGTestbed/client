_deprecated_mux2octet = {
    "amsterdam01": 224,
    "gatech01": 225,
    "grnet01": 230,
    "neu01": 248,
    "seattle01": 250,
    "ufmg01": 251,
    "utah01": 252,
    "wisc01": 253,
}

octets = [224, 225, 246, 254]

mux2peers = {
    "amsterdam01": [60, 61],  # announce only to BIT
    "seattle01": [101],  # announce only to RGNet
    "ufmg01": [16],  # announce only to RNP
}

mux2id = {"amsterdam01": 5,
        "clemson01": 16,
        "gatech01": 6,
        "grnet01": 9,
        "neu01": 14,
        "seattle01": 1,
        "utah01": 17,
        "uw01": 10,
        "wisc01": 11}
