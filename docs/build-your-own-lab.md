## Building this lab on your server or VM

This is a high-level guide to help a user re-create the Cisco Live lab in their own environment. The steps outlined below do not describe all required steps in detail, but rather provide a roadmap to getting it done. Generally speaking all the necessary [configuration files](../infrastructure/) are in this repository. We recommend working with an AI assistant, which can explore the repo structure and files in detail to help complete the steps below.

### Hardware/VM Requirements

1. **Topology Host**: Ubuntu server or VM with at least 24 vCPU and 64GB of memory. CL lab uses Ubuntu 22.04 and 32vCPU + 96GB memory
   
2. **Jalapeno VM**: Ubuntu VM with 4vCPU and 8GB of memory. CL lab runs this as a standalone VM, but it could be a nested VM living on **Topology Host**

### Constructing the lab

#### Topology Host - containerlab and XRd
1. Install **containerlab**: https://containerlab.dev/install/

2. Download XRd *control plane* image from Cisco CCO: https://www.cisco.com/c/en/us/support/routers/ios-xrd/series.html#~tab-downloads

4. Load the XRd image:
```bash
docker load -i <image file>
```

#### Topology Host - vrnetlab and SONiC VS

1. Install **vrnetlab**, which will allow us to *dockerize* a sonic-vs KVM image
```bash
git clone https://github.com/srl-labs/vrnetlab
```

2. Download SONiC VS image: https://sonic.software/
  
  - **Branch Master**: CL lab uses the **sonic-vs.img.gz** KVM image which we *dockerize* with vrnetlab. 
  - The next version of the CL lab will use **docker-sonic-vs.gz**, but our Ansible config workflow will change.

3. Gunzip then move or copy the sonic-vs KVM file into the *`vrnetlab/sonic/`* directory. Re-name it as sonic-vs.qcow2
```bash
gunzip sonic-vs.img.gz
mv sonic-vs.img vrnetlab/sonic/sonic-vs.qcow2
```

4. cd into the vrnetlab/sonic directory and run *`make`* to dockerize the qcow2 image:
```bash
cd vrnetlab/sonic/
make
```

5. docker images command should now show your XRd and vrnetlab sonic images:
```bash
docker images
```

#### Topology Host - create DC01 VMs

There are quite a few options for creating the nested **DC01 VM** qcow2 images. 
Something along these lines: https://askubuntu.com/questions/1480090/how-to-install-ubuntu-22-04-as-guest-in-kvm
Or just ask your favorite AI for a procedure.

1. Use the virsh xml files in [infrastructure/vms](../infrastructure/vms/) to define and start *`dc01-vm-0x`* virsh nets and VMs

```bash
virsh net-define <net.xml>
virsh net-start <netname>

virsh define <vm.xml>
# etc.
```

2. Run the [bridges.sh](../infrastructure/vms/bridges.sh) shell script to activate the bridges and VMs
```bash
cd infrastructure/vms/
./bridges.sh
```

#### Topology Host - install k8s and cilium on DC01 VMs

1. Once the VMs are deployed you'll need to console in using an app like *Screen Sharing* on a Mac and give them IP addresses. *virsh dumpxml* output will display which port to connect your Screen Share to
```bash
virsh dumpxml dc01-vm-00
```
look for something like:
```bash
    <graphics type='vnc' port='5900' autoport='yes' listen='0.0.0.0' passwd='cisco123'>
      <listen type='address' address='0.0.0.0'/>
    </graphics>
```

2. Edit the yaml file in /etc/netplan/ to match the netplan yaml files in the vms folders
   [Example](../infrastructure/vms/dc01-vm-00/dc01-vm-00-netplan.yaml)

3. Apply netplan config
```bash
sudo netplan apply
```

4. Add users and needed (sudo user add <name>) and edit /etc/hosts and /etc/hostname

5. You should be able to ssh to the VM now

6. Install K8s [instructions](../lab_3/k8s-install-instructions.md)

7. Install Cilium Enterprise - please contact your Isovalent support team for access

#### Launch lab topology

```bash
cd lab_1/
clab deploy -t lab_1-topology.clab.yaml
```