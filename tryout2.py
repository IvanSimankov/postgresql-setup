import sys
import paramiko

key_filepath = "C:/Users/ivans/.ssh/id_rsa"
username = "root"

def execute_ssh_command(host, command, key_filepath, username="root"):
    try:
        print(f"\n📤 [SSH] Выполняем команду: {command}")
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(host, username=username, key_filename=key_filepath)
        stdin, stdout, stderr = ssh_client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        ssh_client.close()
        if output.strip():
            print(f"✅ [stdout]: {output.strip()}")
        if error.strip():
            print(f"⚠️ [stderr]: {error.strip()}")
        return output
    except Exception as e:
        print(f"❌ Ошибка подключения или выполнения команды: {e}")
        return None

def get_server_load(host, key_filepath):
    command = "uptime"
    output = execute_ssh_command(host, command, key_filepath)
    if output:
        load = output.split("load average:")[1].strip().split(",")[0]
        return float(load)
    return float('inf')

def detect_os_type(host, key_filepath):
    os_release = execute_ssh_command(host, "cat /etc/os-release", key_filepath)
    if os_release:
        if "Debian" in os_release or "Ubuntu" in os_release:
            return "debian"
        elif "AlmaLinux" in os_release or "CentOS" in os_release:
            return "centos"
    return "unknown"

def install_postgresql(host, key_filepath, os_type):
    if os_type == "debian":
        command = "apt-get update && apt-get install -y postgresql"
    elif os_type == "centos":
        command = "dnf install -y postgresql-server"
    else:
        print(f"⚠️ Неизвестная система: {os_type}")
        return False

    output = execute_ssh_command(host, command, key_filepath)
    return output is not None and "command not found" not in output.lower()

def configure_postgresql(host, key_filepath, os_type):
    if os_type == "debian":
        conf = "/etc/postgresql/12/main/postgresql.conf"
        hba = "/etc/postgresql/12/main/pg_hba.conf"
        service = "postgresql"
    else:  # centos
        conf = "/var/lib/pgsql/data/postgresql.conf"
        hba = "/var/lib/pgsql/data/pg_hba.conf"
        service = "postgresql"

    commands = [
        f"echo \"listen_addresses = '*'\" >> {conf}",
        f"echo \"host all all 0.0.0.0/0 md5\" >> {hba}",
        f"systemctl restart {service}"
    ]
    for cmd in commands:
        if execute_ssh_command(host, cmd, key_filepath) is None:
            return False
    return True

def create_student_user(host, key_filepath, server_ip, os_type):
    if os_type == "debian":
        hba = "/etc/postgresql/12/main/pg_hba.conf"
        service = "postgresql"
    else:
        hba = "/var/lib/pgsql/data/pg_hba.conf"
        service = "postgresql"

    create_user_cmd = (
        f"sudo -u postgres psql -d postgres -c \"DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'student') "
        f"THEN CREATE ROLE student LOGIN PASSWORD 'password'; END IF; END $$;\""
    )
    if execute_ssh_command(host, create_user_cmd, key_filepath):
        execute_ssh_command(host, f"echo \"host all student {server_ip}/32 md5\" >> {hba}", key_filepath)
        execute_ssh_command(host, f"systemctl restart {service}", key_filepath)
        return True
    return False

def check_postgresql(host, key_filepath):
    cmd = "sudo -u postgres psql -c \"SELECT 1;\""
    output = execute_ssh_command(host, cmd, key_filepath)
    return output and "1" in output

def main():
    if len(sys.argv) != 2:
        print("❗ Укажите IP-адреса серверов через запятую: python script.py \"ip1,ip2\"")
        return

    servers = sys.argv[1].split(",")
    if len(servers) != 2:
        print("❗ Нужно указать ровно два сервера.")
        return

    print("📊 Оцениваем нагрузку на серверах...")
    server_loads = {host: get_server_load(host, key_filepath) for host in servers}
    for s, l in server_loads.items():
        print(f"   {s} → нагрузка: {l}")

    selected_host = min(server_loads, key=server_loads.get)
    second_ip = [s for s in servers if s != selected_host][0]

    print(f"\n✅ Выбран сервер: {selected_host}")
    os_type = detect_os_type(selected_host, key_filepath)
    print(f"🧠 Обнаружена ОС: {os_type}")

    if not install_postgresql(selected_host, key_filepath, os_type):
        print("❌ Ошибка установки PostgreSQL.")
        return
    print("📦 PostgreSQL установлен.")

    if not configure_postgresql(selected_host, key_filepath, os_type):
        print("❌ Ошибка настройки PostgreSQL.")
        return
    print("⚙️ PostgreSQL настроен.")

    if not create_student_user(selected_host, key_filepath, second_ip, os_type):
        print("❌ Не удалось создать пользователя 'student'.")
    else:
        print("👤 Пользователь 'student' создан и ограничен по IP.")

    print("\n🔍 Проверка SELECT 1:")
    if check_postgresql(selected_host, key_filepath):
        print("✅ PostgreSQL работает корректно!")
    else:
        print("❌ Ошибка при выполнении SELECT 1.")

    print("\n🎉 Готово!")

if __name__ == "__main__":
    main()



