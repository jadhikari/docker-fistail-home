# Migration Rules - KEEP IT SIMPLE

## 🚨 NEVER DELETE MIGRATION FILES

**Rule #1: Never delete migration files in production OR development**

This is the ONLY rule you need to remember. If you delete migration files, Django loses track of what has been applied to the database, causing the exact errors you've been getting.

## ✅ What to do instead

### If you get "relation already exists" error:
```bash
# DON'T delete migration files
# DO THIS instead:
python manage.py migrate --fake-initial
```

### If you need to fix migration conflicts:
```bash
# 1. Check what migrations exist
python manage.py showmigrations

# 2. If tables exist but migrations are missing, fake them:
python manage.py migrate --fake

# 3. If you need to create new migrations:
python manage.py makemigrations
python manage.py migrate
```

## 📁 Keep your migration files safe

```
backend/
├── accounts/migrations/
│   ├── __init__.py          ← Keep this
│   ├── 0001_initial.py      ← Keep this
│   └── 0002_add_field.py    ← Keep this
├── customer/migrations/
│   ├── __init__.py          ← Keep this
│   └── 0001_initial.py      ← Keep this
└── ...
```

## 🎯 Simple Workflow

1. **Make changes to your models**
2. **Create migration**: `python manage.py makemigrations`
3. **Apply migration**: `python manage.py migrate`
4. **Commit migration files to git**

That's it! No complex tools needed.

## 🚨 Emergency Fix

If you accidentally deleted migration files:

1. **Don't panic**
2. **Restore from git**: `git checkout HEAD -- */migrations/`
3. **If that doesn't work, fake the migrations**:
   ```bash
   python manage.py migrate --fake
   ```

## 📝 Remember

- ✅ Keep all migration files
- ✅ Use `--fake` when needed
- ✅ Test in development first
- ❌ Never delete migration files
- ❌ Never skip migration numbers

**That's all you need to know!** 