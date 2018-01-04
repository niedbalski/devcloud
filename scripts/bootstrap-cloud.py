#!/usr/bin/env python3

import shade
import argparse
import sys


def create_resources(config):
    shade.simple_logging(debug=True)

    cloud = shade.openstack_cloud(cloud=config.cloud)

    domain_id = cloud.get_domain('default').id
    project_id = cloud.get_project('service').id

    user = cloud.get_user('demo')
    if not user:
        user = cloud.create_user(name='demo',
                                 domain_id=domain_id,
                                 password='pass')

    granted = cloud.grant_role("admin", user="demo", project="service")

    flavor_tiny = cloud.get_flavor("m1.tiny")
    if not flavor_tiny:
        flavor_tiny = cloud.create_flavor("m1.tiny", 512, 1, 1)

    flavor_small = cloud.get_flavor("m1.small")
    if not flavor_small:
        flavor_small = cloud.create_flavor("m1.small", 1024, 2, 2)

    image = cloud.get_image(config.image_name)
    if not image:
        image = cloud.create_image(config.image_name,
                                   filename=config.image_filename,
                                   container_format="bare",
                                   disk_format="qcow2",
                                   wait=True, is_public=True)

    updated = cloud.update_image_properties(image=image,
                                            os_command_line='console=ttyAMA0',
                                            hw_disk_bus='scsi',
                                            hw_scsi_model='virtio-scsi',
                                            hw_firmware_type='uefi')

    external_network = cloud.get_network("ext-net")
    if not external_network:
        external_network = cloud.create_network("ext-net", external=True,
                                                provider={
                                                    'physical_network': "external",
                                                    'network_type': "flat"
                                                })

    external_floating = cloud.get_subnet("ext-net-floating")
    if not external_floating:
        external_floating = cloud.create_subnet("ext-net",
                                                subnet_name="ext-net-floating",
                                                enable_dhcp=False,
                                                allocation_pools=[{
                                                    "start": config.floating_range_start,
                                                    "end": config.floating_range_end,
                                                }],
                                                gateway_ip=config.floating_gateway_ip,
                                                cidr=config.floating_cidr)

    # Create network for demo project
    demo_network = cloud.get_network("demo-net")
    if not demo_network:
        demo_network = cloud.create_network("demo-net",
                                            project_id=project_id,
                                            provider={'network_type': "vxlan"})

    demo_subnet = cloud.get_subnet("demo-subnet")
    if not demo_subnet:
        demo_subnet = cloud.create_subnet(demo_network.id,
                                          subnet_name="demo-subnet",
                                          gateway_ip="192.168.1.1",
                                          enable_dhcp=True,
                                          cidr="192.168.1.0/24",
                                          dns_nameservers=["8.8.8.8"])

    router = cloud.get_router("demo-router")
    if not router:
        router = cloud.create_router(
            name="demo-router",
            ext_gateway_net_id=cloud.get_network(
                "ext-net").id)
        interface = cloud.add_router_interface(router,
                                               subnet_id=cloud.get_subnet(
                                                   "demo-subnet").id)

    security_group = cloud.get_security_group("default")

    allow_ping = cloud.create_security_group_rule(security_group.id,
                                                  protocol="icmp",
                                                  direction="ingress")

    allow_ssh = cloud.create_security_group_rule(security_group.id,
                                                 protocol="tcp",
                                                 direction="ingress",
                                                 port_range_min=22,
                                                 port_range_max=22)

    keypair = cloud.get_keypair("demo-default")
    if not keypair:
        keypair = cloud.create_keypair("demo-default",
                                       config.public_key_file.read())

    # Create a instance
    server = cloud.create_server(
        name="demo-vm",
        image=image.id,
        wait=True,
        auto_ip=False,
        flavor=flavor_small.id,
        security_groups=[security_group.id, 'default'],
        network=demo_network.id,
        key_name="demo-default",
    )

    # Assign a floating ip to the server
    floating_ip_address = cloud.add_auto_ip(
        server,
        wait=True,
    )

    print('Access your server at cirros@{}'.format(
        floating_ip_address,
    ))


def parse_args():
    parser = argparse.ArgumentParser(
        description=" This script will create the base flavors,"
        "upload a base cirros image, create a new user (demo),"
        "setup the external network and also a private network"
        "for the demo user (and its corresponding router).")

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)

    parser.add_argument('--floating-range-start', dest='floating_range_start',
                        required=True, type=str)
    parser.add_argument('--floating-range-end', dest='floating_range_end',
                        required=True, type=str)
    parser.add_argument('--floating-gateway', dest='floating_gateway_ip',
                        required=True, type=str)
    parser.add_argument('--floating-cidr', dest='floating_cidr',
                        required=True, type=str)
    parser.add_argument('--public-key-file', dest='public_key_file',
                        required=True, type=argparse.FileType('r'))
    parser.add_argument('--cloud', '-c', dest='cloud',
                        required=True, type=str)
    parser.add_argument('--image-filename', dest="image_filename",
                        required=True)
    parser.add_argument('--image-name', dest="image_name", required=True)

    return parser.parse_args()


def main():
    args = parse_args()
    create_resources(args)

if __name__ == "__main__":
    main()
