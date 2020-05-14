experiment = 'codechef'
with_df = True
if experiment == 'codechef':
    labels = ['ac', 'wa', 're', 'tle']
elif experiment == 'codeforces':
    labels = ['OK', 'WRONGANSWER', 'MEMORYLIMITEXCEEDED', 'TIMELIMITEXCEEDED', 'RUNTIMEERROR']
elif experiment == 'promise':
    labels = ['0', '1']
else:
    print('Experiment cannot recognized')
    raise ValueError

save_dir = './datas/'
original_data_dir = './codes'


