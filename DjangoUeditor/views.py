#coding:utf-8
from django.http import HttpResponse
import settings as USettings
import os
import json
from utils import GenerateRndFilename
from django.views.decorators.csrf import csrf_exempt
from .models import ImageStore,FileStore
from common.utils import login_required


#上传附件
@csrf_exempt
@login_required
def UploadFile(request,uploadtype,uploadpath):
    if not request.method=="POST":
        return HttpResponse(json.dumps(u"{'state:'ERROR'}"),content_type="application/javascript")
    state="SUCCESS"
    file=request.FILES.get("upfile",None)
    #如果没有提交upfile则返回错误
    if file is None:
        return HttpResponse(json.dumps(u"{'state:'ERROR'}"),content_type="application/javascript")
    #取得上传的文件的原始名称
    names=file.name.split('.')
    original_name,original_ext=".".join(names[0:-1]),names[-1]
    #类型检验
    if uploadtype=="image" or uploadtype=="scrawlbg":
        allow_type= USettings.UEditorSettings["images_upload"]['allow_type']
    else:
        allow_type= USettings.UEditorSettings["files_upload"]['allow_type']
    if not original_ext in allow_type:
        state=u"服务器不允许上传%s类型的文件。" % original_ext
    #大小检验
    max_size=USettings.UEditorSettings["images_upload"]['max_size']
    if max_size!=0:
        from utils import FileSize
        MF=FileSize(max_size)
        if file.size>MF.size:
            state=u"上传文件大小不允许超过%s。" % MF.FriendValue
    #所有检测完成后写入文件
    if not state=="SUCCESS":
        return HttpResponse(json.dumps({
            "state":state
        }),content_type="application/javascript")
    #返回数据

    if uploadtype=="image" or uploadtype=="scrawlbg":
        store=ImageStore.get_by_file(request.user,file,os.path.join(uploadpath,file.name))
        rInfo={
            'url':store.url,    #保存后的文件名称
            'title':request.POST.get("pictitle",file.name),       #文件描述，对图片来说在前端会添加到title属性上
            'original':file.name,      #原始文件名
            'state':state           #上传状态，成功时返回SUCCESS,其他任何值将原样返回至图片上传框中
        }
        #保存到文件中
    else:
        store=FileStore.get_by_file(request.user,file,os.path.join(uploadpath,file.name))
        rInfo={
            'url':store.url,         #保存后的文件名称
            'original':file.name,         #原始文件名
            'filetype':original_ext,
            'state':state               #上传状态，成功时返回SUCCESS,其他任何值将原样返回至图片上传框中
        }
    if uploadtype=="scrawlbg":#上传涂鸦背景
        return HttpResponse(u"<script>parent.ue_callback('%s','%s');</script>" % (rInfo["url"],rInfo["state"]))
    else:#上传文件与图片
        return HttpResponse(json.dumps(rInfo),content_type="application/javascript")


#图片文件管理器
@csrf_exempt
@login_required
def ImageManager(request,imagepath):
    if not request.method!="GET":
        return HttpResponse(json.dumps(u"{'state:'ERROR'}"),content_type="application/javascript")
    #取得动作
    action=request.GET.get("action","get")
    if action=="get":
        return HttpResponse(ReadDirImageFiles(imagepath,request.user),content_type="application/javascript")


def ReadDirImageFiles(path,user):
    # print path
    imgs=ImageStore.objects.filter(
        owner=user,
        file__startswith=path
    )
    return "ue_separate_ue".join([img.url for img in imgs])

#遍历所有文件清单
# def ReadDirImageFiles(path):
#     files=""
#     dirs=os.listdir(path)
#     for f in dirs:
#         ext=os.path.splitext(f)[1][1:]
#         if ext!="":
#             if ext in USettings.UEditorSettings["images_upload"]["allow_type"]:
#                 if files!="":
#                     files+="ue_separate_ue"
#                 files+=f
#     return files


#抓取远程图片
@csrf_exempt
@login_required
def RemoteCatchImage(request,imagepath):
    upfile_url=request.POST.get("upfile",None)
    if upfile_url is None:
        return HttpResponse(json.dumps("{'state:'ERROR'}"),content_type="application/javascript")

    img=ImageStore.get_by_url(
        user=request.user,
        url=upfile_url,
        path=imagepath,
        checker=lambda url,filename,result:filename.split(".")[-1].lower() in USettings.UEditorSettings['images_upload']['allow_type']
    )
    if not img:
        HttpResponse(json.dumps({"tip": u"图片抓取错误"}),content_type="application/javascript")

    #将抓取到的文件写入文件
    rInfo={
        'url': img.url,                      # 新地址一ue_separate_ue新地址二ue_separate_ue新地址三',
        'srcUrl':upfile_url,                    #原始地址一ue_separate_ue原始地址二ue_separate_ue原始地址三',
        'tip':u'远程图片抓取成功！'           #'状态提示'
    }

    return HttpResponse(json.dumps(rInfo),content_type="application/javascript")


#搜索视频
@csrf_exempt
@login_required
def SearchMovie(request):
    Searchkey =request.POST.get("searchKey",None)
    if Searchkey is None:
        return HttpResponse(u"错误！")
    Searchtype=request.POST.get("videoType","")
    import urllib
    Searchkey=urllib.quote(Searchkey.encode("utf8"))
    Searchtype=urllib.quote(Searchtype.encode("utf8"))
    try:
        htmlcontent=urllib.urlopen(u'http://api.tudou.com/v3/gw?method=item.search&appKey=myKey&format=json&kw=%s&pageNo=1&pageSize=20&channelId=%s&inDays=7&media=v&sort=s' % (Searchkey,Searchtype))
        return HttpResponse(htmlcontent)
    except Exception,E:
        return HttpResponse(E.message)


#涂鸦功能上传
@csrf_exempt
@login_required
def scrawlUp(request,uploadpath):
    action=request.GET.get("action","")
    #背景上传
    if action=="tmpImg":
        return UploadFile(request,"scrawlbg", uploadpath)
    else:       #处理涂鸦合成相片上传
        # try:
        content=request.POST.get("content","")
        import base64

        OutputFile=GenerateRndFilename("scrawl.png")
        ##适配原始FileStorage

        image=ImageStore.get_by_file(
            user=request.user,
            file=base64.decodestring(content),
            file_name=os.path.join(uploadpath,OutputFile)
        )
        rInfo={
            "url":image.url,
            "state":"SUCCESS"
        }
        return HttpResponse(json.dumps(rInfo),content_type="application/javascript")
