import pyperclip

result = []
with open('temp.txt', 'r') as file_obj:
    for next_line in file_obj:
        result.append(next_line[next_line.find("@"):])
result.sort(key=str.lower)



pyperclip.copy(''.join(result))