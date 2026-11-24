import sys,glob
from PIL import Image
d=sys.argv[1]; fs=sorted(glob.glob(d+'/t_*.png'), key=lambda f: float(f.split('t_')[1][:-4]))
w=360;h=640;cols=5;rows=(len(fs)+cols-1)//cols
S=Image.new('RGB',(w*cols,h*rows))
for i,f in enumerate(fs):
    S.paste(Image.open(f).resize((w,h)),((i%cols)*w,(i//cols)*h))
S.save(d+'/sheet.png');print(len(fs))
