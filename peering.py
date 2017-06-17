import jinja2
import json
import jsonschema
import os
import subprocess
import sys


class AnnouncementController(object):
    def __init__(self, bird_cfg_dir, bird_sock, schema_fn):
        with open(schema_fn) as fd:
            self.schema = json.load(fd)
        self.bird_cfg_dir = str(bird_cfg_dir)
        self.bird_sock = str(bird_sock)
        self.config_template = self.__load_config_template()
        self.__create_routes()

    def __load_config_template(self):
        path = os.path.join(self.bird_cfg_dir, 'templates')
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(path))
        return env.get_template('export_mux_pfx.jinja2')

    def __config_file(self, prefix, mux):
        fn = 'export_%s_%s.conf' % (mux, prefix.replace('/', '-'))
        return os.path.join(self.bird_cfg_dir, 'prefix-filters', fn)

    def __create_routes(self):
        path = os.path.join(self.bird_cfg_dir, 'route-announcements')
        os.makedirs(path, exist_ok=True)
        for pfx in self.schema['definitions']['allocatedPrefix']['enum']:
            fpath = os.path.join(path, pfx.replace('/', '-'))
            fd = open(fpath, 'w')
            fd.write('route %s unreachable;\n' % pfx)
            fd.close()

    def validate(self, announcement):
        jsonschema.validate(announcement, self.schema)

    def deploy(self, announcement):
        self.validate(announcement)
        self.update_config(announcement)
        self.reload_config()

    def update_config(self, announcement):
        self.validate(announcement)
        for prefix, announce in announcement.items():
            for mux in announce.get('withdraw', list()):
                self.withdraw(prefix, mux)
            for spec in announce.get('announce', list()):
                self.announce(prefix, spec)

    def withdraw(self, prefix, mux):
        os.unlink(self.__cfg_fpath(prefix, mux))

    def announce(self, prefix, spec):
        for mux in spec['muxes']:
            with open(self.__config_file(prefix, mux), 'w') as fd:
                fd.write(self.config_template.render(prefix=prefix, spec=spec))

    def reload_config(self):
        cmd = 'birdc -s %s' % self.bird_sock
        proc = subprocess.Popen(cmd.split(),
                                stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        _stdout, _stderr = proc.communicate('configure\n')


if __name__ == '__main__':
    controller = AnnouncementController('./bird-test', None, 'announcement_schema.json')
    with open(sys.argv[1], 'r') as fd:
        announcement = json.load(fd)
    controller.update_config(announcement)
