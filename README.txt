Как запустить у себя на пк

# Установить в виртуальное окружение
python -m venv venv
на Windows: venv\Scripts\activate

###Не трогай
source venv/bin/activate  
###

pip install -r requirements.txt

Потом в 3 разных терминалах пишешь 

python tg_bot\bot.py

python tg_bot\api_server.py

python manage.py runserver

Данные от admin Django
l: admin
p: admin123