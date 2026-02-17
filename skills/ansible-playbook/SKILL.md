---
name: ansible-playbook
description: Generate Ansible playbooks for multi-machine automation, configuration management, application deployment, and infrastructure setup. Use when managing multiple machines, deploying applications across servers, or need idempotent configuration management.
triggers: ["ansible", "provision", "deploy", "multiple machines", "infrastructure", "configuration management", "multi-server"]
category: automation
execution: claude-code
allowed-tools: ["Bash(ansible*)", "Read", "Write"]
---

# Ansible Playbook Generator

Creates Ansible playbooks for infrastructure automation and configuration management.

## When to Use
- Manage multiple servers
- Deploy applications consistently
- Configure systems automatically
- Ensure idempotent operations
- Infrastructure as Code
- Orchestrate complex deployments
- Maintain configuration consistency

## Ansible Basics

### Inventory File (hosts.ini)
```ini
[webservers]
web1.example.com
web2.example.com

[databases]
db1.example.com

[all:vars]
ansible_user=admin
ansible_python_interpreter=/usr/bin/python3
```

### Basic Playbook Structure
```yaml
---
- name: Playbook Name
  hosts: target_group
  become: yes  # Run as sudo
  vars:
    variable_name: value

  tasks:
    - name: Task description
      module_name:
        parameter: value

  handlers:
    - name: Handler name
      service:
        name: service_name
        state: restarted
```

## Common Playbook Patterns

### Install and Configure Web Server
```yaml
---
- name: Setup NGINX Web Server
  hosts: webservers
  become: yes

  tasks:
    - name: Install NGINX
      apt:
        name: nginx
        state: present
        update_cache: yes

    - name: Copy configuration file
      copy:
        src: files/nginx.conf
        dest: /etc/nginx/nginx.conf
        owner: root
        group: root
        mode: '0644'
      notify: Restart NGINX

    - name: Ensure NGINX is running
      service:
        name: nginx
        state: started
        enabled: yes

  handlers:
    - name: Restart NGINX
      service:
        name: nginx
        state: restarted
```

### Deploy Application
```yaml
---
- name: Deploy Python Application
  hosts: appservers
  become: yes
  vars:
    app_dir: /opt/myapp
    app_user: appuser

  tasks:
    - name: Create application user
      user:
        name: "{{ app_user }}"
        system: yes
        shell: /bin/bash

    - name: Create application directory
      file:
        path: "{{ app_dir }}"
        state: directory
        owner: "{{ app_user }}"
        group: "{{ app_user }}"

    - name: Install Python dependencies
      apt:
        name:
          - python3
          - python3-pip
          - python3-venv
        state: present

    - name: Clone application repository
      git:
        repo: https://github.com/user/app.git
        dest: "{{ app_dir }}"
        version: main
      become_user: "{{ app_user }}"

    - name: Install Python packages
      pip:
        requirements: "{{ app_dir }}/requirements.txt"
        virtualenv: "{{ app_dir }}/venv"
      become_user: "{{ app_user }}"

    - name: Copy systemd service file
      template:
        src: templates/app.service.j2
        dest: /etc/systemd/system/myapp.service
      notify: Restart application

    - name: Enable and start application service
      systemd:
        name: myapp
        enabled: yes
        state: started
        daemon_reload: yes

  handlers:
    - name: Restart application
      systemd:
        name: myapp
        state: restarted
```

### Database Setup
```yaml
---
- name: Setup PostgreSQL Database
  hosts: databases
  become: yes
  vars:
    db_name: myapp
    db_user: myappuser
    db_password: "{{ vault_db_password }}"

  tasks:
    - name: Install PostgreSQL
      apt:
        name:
          - postgresql
          - postgresql-contrib
          - python3-psycopg2
        state: present

    - name: Ensure PostgreSQL is running
      service:
        name: postgresql
        state: started
        enabled: yes

    - name: Create database
      postgresql_db:
        name: "{{ db_name }}"
        state: present
      become_user: postgres

    - name: Create database user
      postgresql_user:
        name: "{{ db_user }}"
        password: "{{ db_password }}"
        db: "{{ db_name }}"
        priv: ALL
        state: present
      become_user: postgres

    - name: Configure PostgreSQL for remote connections
      lineinfile:
        path: /etc/postgresql/14/main/postgresql.conf
        regexp: '^#?listen_addresses'
        line: "listen_addresses = '*'"
      notify: Restart PostgreSQL

  handlers:
    - name: Restart PostgreSQL
      service:
        name: postgresql
        state: restarted
```

### System Updates and Patching
```yaml
---
- name: Update All Servers
  hosts: all
  become: yes

  tasks:
    - name: Update apt cache
      apt:
        update_cache: yes
        cache_valid_time: 3600
      when: ansible_os_family == "Debian"

    - name: Upgrade all packages
      apt:
        upgrade: dist
      when: ansible_os_family == "Debian"

    - name: Check if reboot required
      stat:
        path: /var/run/reboot-required
      register: reboot_required

    - name: Reboot if required
      reboot:
        msg: "Reboot by Ansible after updates"
        pre_reboot_delay: 5
      when: reboot_required.stat.exists
```

### Docker Container Deployment
```yaml
---
- name: Deploy Docker Containers
  hosts: docker_hosts
  become: yes

  tasks:
    - name: Install Docker
      apt:
        name:
          - docker.io
          - docker-compose
        state: present

    - name: Ensure Docker is running
      service:
        name: docker
        state: started
        enabled: yes

    - name: Copy docker-compose file
      copy:
        src: files/docker-compose.yml
        dest: /opt/app/docker-compose.yml

    - name: Start Docker containers
      docker_compose:
        project_src: /opt/app
        state: present
```

### Configuration Management
```yaml
---
- name: Configure Server Settings
  hosts: all
  become: yes

  tasks:
    - name: Set timezone
      timezone:
        name: America/Chicago

    - name: Configure sysctl parameters
      sysctl:
        name: "{{ item.key }}"
        value: "{{ item.value }}"
        state: present
      loop:
        - { key: 'net.ipv4.ip_forward', value: '1' }
        - { key: 'vm.swappiness', value: '10' }

    - name: Create admin users
      user:
        name: "{{ item }}"
        groups: sudo
        shell: /bin/bash
        state: present
      loop:
        - admin1
        - admin2

    - name: Copy SSH keys
      authorized_key:
        user: "{{ item }}"
        key: "{{ lookup('file', 'files/{{ item }}.pub') }}"
      loop:
        - admin1
        - admin2
```

## Common Modules

### Package Management
```yaml
- name: Install packages (Debian/Ubuntu)
  apt:
    name: package_name
    state: present

- name: Install packages (RedHat/CentOS)
  yum:
    name: package_name
    state: present
```

### Files and Directories
```yaml
- name: Create directory
  file:
    path: /path/to/dir
    state: directory
    owner: user
    group: group
    mode: '0755'

- name: Copy file
  copy:
    src: local/file
    dest: /remote/file
    owner: user
    mode: '0644'

- name: Template file
  template:
    src: template.j2
    dest: /remote/file
```

### Services
```yaml
- name: Manage service
  service:
    name: service_name
    state: started
    enabled: yes
```

### Users and Groups
```yaml
- name: Create user
  user:
    name: username
    groups: group1,group2
    shell: /bin/bash
    state: present
```

### Commands
```yaml
- name: Run command
  command: /path/to/command
  args:
    chdir: /working/dir

- name: Run shell command
  shell: |
    complex
    multi-line
    command
```

## Running Playbooks

### Basic Execution
```bash
# Run playbook
ansible-playbook playbook.yml

# With inventory file
ansible-playbook -i hosts.ini playbook.yml

# Specific hosts
ansible-playbook playbook.yml --limit webservers

# Check mode (dry run)
ansible-playbook playbook.yml --check

# Verbose output
ansible-playbook playbook.yml -v
ansible-playbook playbook.yml -vv
ansible-playbook playbook.yml -vvv
```

### With Variables
```bash
# Pass variables
ansible-playbook playbook.yml -e "variable=value"

# From file
ansible-playbook playbook.yml -e "@vars.yml"

# With vault password
ansible-playbook playbook.yml --ask-vault-pass
```

## Variables

### In Playbook
```yaml
vars:
  app_port: 8080
  app_name: myapp
```

### Separate File (vars.yml)
```yaml
---
app_port: 8080
app_name: myapp
db_host: db.example.com
```

### Using Variables
```yaml
tasks:
  - name: Configure app
    template:
      src: config.j2
      dest: "/etc/{{ app_name }}/config.yml"
```

## Handlers

### Define Handlers
```yaml
handlers:
  - name: Restart NGINX
    service:
      name: nginx
      state: restarted

  - name: Reload systemd
    systemd:
      daemon_reload: yes
```

### Trigger Handlers
```yaml
tasks:
  - name: Update config
    copy:
      src: config
      dest: /etc/config
    notify: Restart NGINX
```

## Conditionals

### When Clause
```yaml
- name: Install on Debian
  apt:
    name: package
  when: ansible_os_family == "Debian"

- name: Run if file exists
  command: /usr/bin/script
  when: some_file.stat.exists
```

## Loops

### Simple Loop
```yaml
- name: Install packages
  apt:
    name: "{{ item }}"
    state: present
  loop:
    - nginx
    - postgresql
    - redis
```

### Dict Loop
```yaml
- name: Create users
  user:
    name: "{{ item.name }}"
    groups: "{{ item.groups }}"
  loop:
    - { name: 'user1', groups: 'admin' }
    - { name: 'user2', groups: 'users' }
```

## Templates (Jinja2)

### Template File (config.j2)
```jinja2
server {
    listen {{ app_port }};
    server_name {{ server_name }};

    location / {
        proxy_pass http://localhost:{{ backend_port }};
    }
}
```

### Use Template
```yaml
- name: Generate config
  template:
    src: config.j2
    dest: /etc/nginx/sites-available/myapp
```

## Secrets (Ansible Vault)

### Create Vault File
```bash
ansible-vault create secrets.yml
```

### Edit Vault
```bash
ansible-vault edit secrets.yml
```

### Use Vault Variables
```yaml
- name: Use secret
  postgresql_user:
    password: "{{ vault_db_password }}"
```

## Best Practices

### Idempotency
- Always aim for idempotent operations
- Use `state` parameters correctly
- Avoid shell commands when modules exist

### Organization
```
project/
├── ansible.cfg
├── inventory/
│   ├── production
│   └── staging
├── playbooks/
│   ├── deploy.yml
│   └── update.yml
├── roles/
│   ├── webserver/
│   └── database/
├── group_vars/
│   └── all.yml
├── host_vars/
└── files/
```

### Use Roles
```yaml
- name: Configure server
  hosts: webservers
  roles:
    - common
    - webserver
    - monitoring
```

### Tags
```yaml
- name: Install packages
  apt:
    name: nginx
  tags:
    - packages
    - nginx

# Run specific tags
# ansible-playbook playbook.yml --tags nginx
```

## Testing

### Check Syntax
```bash
ansible-playbook playbook.yml --syntax-check
```

### Dry Run
```bash
ansible-playbook playbook.yml --check
```

### Single Host
```bash
ansible-playbook playbook.yml --limit host1
```

## Related Skills
- bash-automation: Scripts for simpler tasks
- systemd-service: Services on single machines
- cron-manager: Simple scheduled tasks
