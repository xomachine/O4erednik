O4erednik
=========

Queue functional for Gaussian 03


The application provides possibility to submit your Gaussian 03 jobs into a queue and calculate them one by one.
Queue of jobs can be shared between computers of local network with this application and gaussian installed.
You also can submit jobs via GaussView, if you will set path to the fake g03 file. 
At this moment, supported only Russian language.

Experimentally added support of remote sending jobs to another computer without starting it on this one
(client mode, server mode), but not tested yet at all. BE CAREFUL


Программа позволяет выполнять несколько задач для Gaussian 03 в режиме очереди, а также разделять нагрузку между
компьютерами локальной сети, на которых тоже установленна данная программа и Gaussian, что позволяет более эффективно
использовать процессорное время (особенно в случае большого количества небольших заданий). Существует возможность отправки
заданий в очередь непосредственно из GaussView, через эмулятор g03 файла из програмного пакета Gaussian.

Экспериментально добавленна возможность работы в режиме клиента и сервера, когда клиентское приложение не выполняет
задач, а лишь отправляет их на компьютер с серверным приложением. Данный режим еще совсем не тестировался, будьте осторожны!
