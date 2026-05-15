import os
import django
from django.db import connection
from django.core.management import call_command
import shutil

# 1. Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "e4tech.settings")
django.setup()

def wipe_and_rebuild():
    print("⚠️  STARTING POSTGRESQL RESET...")

    # 2. Wipe the Database (Drop all tables)
    with connection.cursor() as cursor:
        print("🔥 Dropping all tables (Schema Public)...")
        cursor.execute("DROP SCHEMA public CASCADE;")
        cursor.execute("CREATE SCHEMA public;")
    print("✅ Database Wiped Clean.")

    # 3. Delete Old Migration Files
    print("\n🧹 Cleaning Migration Files...")
    migration_dir = os.path.join('api', 'migrations')
    if os.path.exists(migration_dir):
        for filename in os.listdir(migration_dir):
            if filename != '__init__.py' and filename != '__pycache__':
                file_path = os.path.join(migration_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"   - Error deleting {filename}: {e}")
    print("✅ Migration files cleaned.")

    # 4. Rebuild Everything
    print("\n🏗️  Rebuilding Database...")
    call_command('makemigrations', 'api')
    call_command('migrate')
    
    # 5. Populate Data
    print("\n🌱 Populating Roles & Admin...")
    from api.models import Role, Department, User
    
    # Create Roles & Depts
    roles = ['IT Admin', 'Student', 'Department Coordinator', 'Event Coordinator']
    for r in roles: Role.objects.get_or_create(name=r)
    
    depts = ['Computer Science', 'Civil', 'Mechanical']
    for d in depts: Department.objects.get_or_create(name=d)

    # Create Superuser
    if not User.objects.filter(email='admin@college.edu').exists():
        admin_user = User.objects.create_superuser('admin@college.edu', 'IT Admin', 'admin')
        admin_user.role = Role.objects.get(name='IT Admin')
        admin_user.save()
        print(f"✅ Created IT Admin: admin@college.edu / admin")

    print("\n🚀 SUCCESS! Your PostgreSQL Database is fixed.")

if __name__ == '__main__':
    wipe_and_rebuild()