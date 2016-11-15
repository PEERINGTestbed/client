class CachingBufferedLineReader(object):
    def __init__(self, fd):
        self.fd = fd
        self.line = None
        self.read = True

    def readline(self):
        if self.read:
            self.line = self.fd.readline()
        else:
            self.read = True
            assert self.line is not None
        return self.line

    def rewind_line(self):
        self.read = False
