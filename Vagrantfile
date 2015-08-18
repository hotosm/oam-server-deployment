# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.require_version ">= 1.6"

Vagrant.configure("2") do |config|
  config.vm.box = "coreos-stable"
  config.vm.box_url = "http://stable.release.core-os.net/amd64-usr/current/coreos_production_vagrant.json"

  config.vm.provider "virtualbox" do |v|
    v.check_guest_additions = false
    v.functional_vboxsf = false
  end

  config.vm.define "core" do |core|
    core.vm.hostname = "core"

    core.vm.provider "virtualbox" do |v|
      v.memory = 1024
      v.cpus = 1
    end

    core.vm.network :private_network, ip: "172.17.8.100"

    core.vm.synced_folder ".", "/vagrant", disabled: true
    core.vm.synced_folder "#{ENV["HOME"]}/.aws", "/home/core/.aws", type: "nfs", mount_options: ["nolock,vers=3,udp"]

    core.vm.provision "file", source: "cloud-config/oam-server-api.yml", destination: "/tmp/vagrantfile-user-data"
    core.vm.provision "shell", inline: "mv /tmp/vagrantfile-user-data /var/lib/coreos-vagrant/", privileged: true
  end
end
