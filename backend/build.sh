set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Build completed successfully!"