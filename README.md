O4erednik
=========

Queue for Quantum Chemistry programs


The application provides possibility to submit your Gaussian, US-GAMESS or NWChem jobs into a queue and calculate them one by one.
Queue of jobs can be shared between computers of local network with this application and gaussian installed.
You also can submit jobs via GaussView, if you will set path to the fake g03 file. 

The application may be expanded for another QC programs (and not only QC) via adding modules to the folder with same name.
(g03.py may be used as example)
You also may hook up other GUI(or work without it), via replacing(or removing) gui.py
At this moment, supported only English and Russian language, but you can help me with translation to other. ;)

Dependences: python3, PyQt4(Only for GUI)


Приложение позволяет выполнять несколько квантово-химических задач в режиме очереди, а также разделять нагрузку между
компьютерами локальной сети, на которых тоже установленна данная программа и расчетная, что позволяет более эффективно
использовать процессорное время (особенно в случае большого количества небольших заданий). Существует возможность отправки
заданий в очередь непосредственно из GaussView, через эмулятор g03 файла из програмного пакета Gaussian.

Приложение можно расширить для работы с другими расчетными(и не только) программами, путем добавления соответствующих
модулей в папку modules.
Кроме того, приложение поддерживает работу с другими графическими интерфейсами (или без них вообще). Этого можно достичь
заменив (или удалив) файл gui.py
На данный момент поддерживаются только русский и англиский языки.

Поддерживаемые программы: Gaussian, US-GAMESS, NWChem

Зависимости: python3, PyQt4(только для графического интерфейса)


