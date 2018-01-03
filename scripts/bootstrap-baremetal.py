#!/usr/bin/env python3

from urllib.parse import urljoin

import argparse
import requests
import json
import sys
import yaml
import os
import logging

logging.basicConfig(level=logging.WARN)
log = logging.getLogger()


class Machine(object):

    def __init__(self, bootstrap, name, config, **extended_config):
        self.bootstrap = bootstrap
        self.name = name
        self.config = config
        self.extended = extended_config

    @property
    def _id(self):
        return self.get_machine_by_name(self.name).get('id')

    @property
    def machine_nics(self):
        return self.bootstrap.do_request("machine/{0}/interface".format(
            self._id))

    def get_nic_by_mac(self, mac_addr):
        for nic in self.machine_nics:
            if nic.get('mac') == mac_addr:
                return nic

    def get_image_by_name(self, name):
        for image in self.bootstrap.images:
            if image.get('name') == name:
                return image

    def get_machine_by_name(self, name):
        for machine in self.bootstrap.machines:
            if machine.get('name') == name:
                return machine

    def get_preseed_by_name(self, name):
        for preseed in self.bootstrap.preseeds:
            if preseed.get('name') == name:
                return preseed

    def configure_nic(self, config):
        nic = self.get_nic_by_mac(config['mac']).get('id')

        request = self.bootstrap.do_put_request(
            "machine/{0}/interface/{1}".format(self._id, nic), {
                "identifier": config['network'],
                "config_type_v4": "static",
                "configured_ipv4": config['ipv4'],
            })

        request.raise_for_status()
        log.debug("Configured NIC:{0} - with params: {1}".format(nic, config))

    def configure(self):
        initrd = self.get_image_by_name(
            self.extended.get("initrd")).get('id')
        kernel = self.get_image_by_name(
            self.extended.get("kernel")).get('id')
        preseed = self.get_preseed_by_name(
            self.extended.get("preseed")).get('id')

        request = self.bootstrap.do_put_request(
            "machine/{0}".format(self._id), {
                "initrd_id": initrd,
                "kernel_id": kernel,
                "preseed_id": preseed,
                "netboot_enabled": True,
            })

        request.raise_for_status()

        log.debug("Configured machine: {0}, with params: {1}".format(
            self.name, self.extended))

        for interface, config in self.config['nics'].items():
            self.configure_nic(config)

    def provision(self):
        request = self.bootstrap.do_post_request("machine/{0}/state".format(
            self._id), {"state": "provision"})
        request.raise_for_status()


class ProvisionerClient(object):

    def __init__(self, config_path, filter_tags=[]):
        self.config_path = config_path
        self.config = yaml.load(config_path)
        self.base_url = urljoin(self.config['provisioner']['url'],
                                "/api/v{0}/".format(
                                self.config['provisioner']['version']))
        self.default_headers = {
            'Authorization': self.config['provisioner']['token']
        }

        self.filter_tags = filter_tags

    def do_request(self, url):
        return requests.get(urljoin(self.base_url, url),
                            headers=self.default_headers).json()

    def do_post_request(self, url, data):
        return requests.post(urljoin(self.base_url, url),
                             headers=self.default_headers,
                             data=json.dumps(data))

    def do_put_request(self, url, data):
        return requests.put(urljoin(self.base_url, url),
                            headers=self.default_headers,
                            data=json.dumps(data))

    @property
    def preseeds(self):
        return self.do_request("preseed?show_all=true")

    @property
    def images(self):
        return self.do_request("image?show_all=true")

    @property
    def machines(self):
        return self.do_request("machine")

    def filter_machines_by_tags(self):
        for tag, tag_config in self.config['machines'].items():
            if tag in self.filter_tags:
                yield tag_config, tag_config['names'].items()

    def configure(self):
        for tag_config, machines in self.filter_machines_by_tags():
            for machine_name, machine_config in machines:
                machine = Machine(self, machine_name, machine_config,
                                  **tag_config)
                machine.configure()

    def provision(self):
        for tag_config, machines in self.filter_machines_by_tags():
            for machine_name, machine_config in machines:
                log.debug("Provisioning machine: {0} with params: {1}".format(
                    machine_name, machine_config))
                machine = Machine(self, machine_name, machine_config,
                                  **tag_config)
                machine.provision()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Configure and provision baremetal"
        "machines for deploying a devcloud")

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)

    parser.add_argument('--log', default='INFO', dest="log",
                        choices=('WARN', 'INFO', 'DEBUG'),
                        help='Logging level to use. Default=%(default)s')

    parser.add_argument("--config", "-c", dest='config',
                        type=argparse.FileType('r'), required=True)

    cmds = parser.add_subparsers(title='commands', dest='which')

    p = cmds.add_parser('baremetal-config')
    p.add_argument("--tags", "-t", dest='tags', nargs='+',
                   default=[], help="List of machine tags")

    p = cmds.add_parser('baremetal-provision')
    p.add_argument("--tags", "-t", dest='tags', nargs='+',
                   default=[], help="List of machine tags")

    return parser.parse_args()


def main():
    args = parse_args()
    log.setLevel(getattr(logging, args.log))

    if args.which in ('baremetal-config', 'baremetal-provision'):
        bootstrap = ProvisionerClient(args.config, filter_tags=args.tags)
        if args.which == 'baremetal-config':
            bootstrap.configure()
        elif args.which == 'baremetal-provision':
            print("foo")
            bootstrap.provision()

if __name__ == "__main__":
    main()
