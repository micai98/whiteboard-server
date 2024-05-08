import time

def timenow():
	return int(time.time())

def hgs(hsize:int=1, text:str="", repeat:int=1):
	for i in range(0, repeat): print("░▒▓" + ((text[:hsize] + " " * (hsize - len(text))) if text != "" else "█"*hsize) + "▓▒░")

def vgs(hsize:int=1, vsize:int=1):
	print("░"*hsize+"\n"+"▒"*hsize+"\n"+"▓"*hsize)
	
def frame(text:str, size:int=0, center:bool=True, elem:list=["╔","╗","╚","╝","═","║", "╠", "╣"]):
	longest = ""
	text = text.replace("\r", "\n\r\n")
	text = text.split("\n")
	for i in text:
		if len(i) > len(longest): longest = i
		
	if size < 1:
		size = len(longest)
	
	print(elem[0]+elem[4]*size+elem[1])
	
	for i in text:
		if i == "\r":
			print(elem[6] + elem[4] * size + elem[7])
		else:
			print(elem[5] + i[:size] + " " * (size-len(i)) + elem[5])
		
		
	print(elem[2]+elem[4]*size+elem[3])
	del text, longest, size, center, elem