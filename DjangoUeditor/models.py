#coding: utf-8

from django.db import models
from django.contrib.admin import widgets as admin_widgets
from widgets import UEditorWidget,AdminUEditorWidget
from utils import MadeUeditorOptions,GenerateRndFilename


class UEditorField(models.TextField):
    """
    百度HTML编辑器字段,初始化时，可以提供以下参数
        initial:初始内容
        plugins:元组
        mode：工具按钮的配置数量，
        toolbars:提供工具按钮列表,取值为列表，如['bold', 'italic'],取值为：mini,normal,full，代表小，一般，全部
        imagePath:图片上传的路径,如"images/",实现上传到"{{MEDIA_ROOT}}/images"文件夹
        filePath:附件上传的路径,如"files/",实现上传到"{{MEDIA_ROOT}}/files"文件夹
        imageManagerPath:图片管理器显示的路径，如果不指定则默认=imagepath
        options：其他UEditor参数，字典类型
        css:编辑器textarea的CSS样式
    """
    def __init__(self,verbose_name=None,width=600,height=300,plugins=(),toolbars="normal",filePath="",imagePath="",scrawlPath="",imageManagerPath="",css="",options={},**kwargs):
        self.ueditor_options=MadeUeditorOptions(width,height,plugins,toolbars,filePath,imagePath,scrawlPath,imageManagerPath,css,options)
        kwargs["verbose_name"]=verbose_name
        super(UEditorField,self).__init__(**kwargs)

    def formfield(self,**kwargs):
        defaults = {'widget': UEditorWidget(**self.ueditor_options)}
        defaults.update(kwargs)
        if defaults['widget'] == admin_widgets.AdminTextareaWidget:
            defaults['widget'] = AdminUEditorWidget(**self.ueditor_options)
        return super(UEditorField, self).formfield(**defaults)


import cStringIO
import PIL.Image
import urlparse
import urllib2
from hashlib import md5
import os
import datetime
from django.core.files.base import ContentFile


def get_image_format(file):
    image_pil=PIL.Image.open(file)
    image_format=image_pil.format.lower()
    image_format="jpg" if image_format=="jpeg" else image_format
    return image_format


def get_content_file_by_url(url,referer=None,is_image=False):
    try:
        headers= {
            'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1478.0 Safari/537.36',
        }
        if referer:
            headers["Referer"]=referer.encode("utf-8")
        req = urllib2.Request(url=url.encode("utf-8"),headers=headers)
        result = cStringIO.StringIO(urllib2.urlopen(req).read())
        file_md5=md5(result.getvalue()).hexdigest()
        file_name=os.path.basename(url)
        if is_image:
            image_format=get_image_format(result)
            # image_name=os.path.basename(url).split(".")
            file_name ="image.%s"%image_format

        return ContentFile(result.getvalue()),file_name,file_md5
    except(urllib2.HTTPError,ValueError):
        return (None,None,None)


def get_content_file_by_file(file):
    result = cStringIO.StringIO(file.read()) if hasattr(file, "read") else cStringIO.StringIO(file)
    file_md5=md5(result.getvalue()).hexdigest()
    return ContentFile(result.getvalue()),file_md5


def get_image_path(instance,file_name):
    today=datetime.date.today()
    print "get_image_path",instance,instance.id,file_name
    dirname=os.path.dirname(file_name)
    basename=os.path.basename(file_name)
    return os.path.join(dirname,str(today.year), str(today.month), str(today.day),GenerateRndFilename(basename))
    return file_name


class BaseFileStore(models.Model):
    source_link=models.URLField(verbose_name=u"源地址",db_index=True,max_length=1024)
    md5=models.CharField(verbose_name=u"MD5",db_index=True,max_length=32)
    created=models.DateTimeField(verbose_name=u"获取时间",blank=True,null=True,auto_now=True)
    owner=models.ManyToManyField("auth.User",verbose_name=u'上传者')

    class Meta(object):
        abstract=True

    def __unicode__(self):
        return u"%s-%s"%(self.source_link,self.md5)

    @property
    def url(self):
        return self.file.url

    @classmethod
    def get_by_file(cls,user,file,file_name):
        result,file_md5=get_content_file_by_file(file)
        if not result:
            return None
        try:
            file=cls.objects.get(md5=file_md5)
        except(cls.DoesNotExist):
                file=cls(
                    source_link=file_name,
                    md5=file_md5
                )
                file.file.save(
                    file_name,
                    result
                )
                # file.save()
        file.owner.add(user)
        return file

    @classmethod
    def get_by_url(cls,user,url,path,referer="",force_refetch=False,checker=None):
        url=urlparse.urljoin(referer,url) if referer else url

        try:
            if force_refetch:
                raise cls.DoesNotExist()
            file=cls.objects.get(source_link=url)
            #~ return image
        except(cls.DoesNotExist):
            result,file_name,file_md5=get_content_file_by_url(url,referer,cls._is_image)
            if callable(checker):
                if not checker(url,file_name,result):
                    return None
            if not result:
                return None
            try:
                file=cls.objects.get(md5=file_md5)
                #~ return image
            except(cls.DoesNotExist):
                # try:
                # print "image",image_name
                # except:
                #     image_name="imagex.jpg"
                file=cls(
                    source_link=url,
                    md5=file_md5,
                )
                file.file.save(
                    os.path.join(path,file_name),
                    result
                )
                # file.save()
        file.owner.add(user)
        return file

    def delete(self,*args,**kwargs):
        self.file.delete(save=False)
        super(BaseFileStore,self).delete(*args,**kwargs)


class FileStore(BaseFileStore):
    file=models.FileField(
        verbose_name=u"文件",
        upload_to=get_image_path
    )
    _is_image=False
    is_image=models.BooleanField(verbose_name=u'是图片',default=False)

    class Meta(object):
        verbose_name=u'文件'


class ImageStore(BaseFileStore):
    file=models.ImageField(
        verbose_name=u"文件",
        upload_to=get_image_path
    )
    _is_image=True
    is_image=models.BooleanField(verbose_name=u'是图片',default=True)

    class Meta:
        verbose_name=u"图片"

#以下支持south
try:
    from south.modelsinspector import add_ignored_fields,add_introspection_rules
    add_introspection_rules([], ["^DjangoUeditor\.models\.UEditorField"])
except:
    pass
