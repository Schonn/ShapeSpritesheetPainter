# Physics Puppet Blender Addon
# Copyright (C) 2021 Pierre
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of  MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

#import blender python libraries
import bpy
import math
import os


#addon info read by Blender
bl_info = {
    "name": "Shape Spritesheet Painter",
    "author": "Pierre",
    "version": (0, 0, 2),
    "blender": (2, 92, 0),
    "description": "Paint masked spritesheets for shape keys",
    "category": "Animation"
    }

#panel class for setting up sprite sheets
class SHASPRI_PT_LayerSetup(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = 'Sprite Layer Setup'
    bl_context = 'objectmode'
    bl_category = 'Shape Spritesheet Painter'
    bpy.types.Scene.SHASPRISpritesheetsFolder = bpy.props.StringProperty(name="Spritesheets Folder",description="Directory to save transparent spritesheets",subtype='DIR_PATH',default='//')
    bpy.types.Scene.SHASPRISpritesheetName = bpy.props.StringProperty(name="Spritesheet Name", description="The name to use for a newly created spritesheet and mask", maxlen=20, default="ShaspriSheet")
    bpy.types.Scene.SHASPRIXResolution = bpy.props.IntProperty(name="Spritesheet Horizontal Resolution", description="Horizontal resolution for new spritesheet", default=2048, subtype='PIXEL')
    bpy.types.Scene.SHASPRIYResolution = bpy.props.IntProperty(name="Spritesheet Vertical Resolution", description="Vertical resolution for new spritesheet", default=2048, subtype='PIXEL')
    bpy.types.Scene.SHASPRILinkOutput = bpy.props.BoolProperty(name="Link Spritesheet Nodegroup to Existing Nodes", description="Attempt to link the spritesheet to the existing node setup", default=True)
    bpy.types.Scene.SHASPRIMakeBaseColor = bpy.props.BoolProperty(name="Create Base Color Image", description="Create a base color image texture in the spritesheets folder and include it in the node setup", default=False)
    bpy.types.Scene.SHASPRIBaseColorName = bpy.props.StringProperty(name="Base Color Image Name", description="Name for the base color image texture", maxlen=20, default="ShaspriBase")

    def draw(self, context):
        self.layout.prop(context.scene,"SHASPRISpritesheetsFolder")
        self.layout.prop(context.scene,"SHASPRISpritesheetName")
        self.layout.prop(context.scene,"SHASPRIXResolution")
        self.layout.prop(context.scene,"SHASPRIYResolution")
        self.layout.prop(context.scene,"SHASPRIMakeBaseColor")
        self.layout.prop(context.scene,"SHASPRIBaseColorName")
        self.layout.prop(context.scene,"SHASPRILinkOutput")
        self.layout.operator('shaspri.addmaskedspritelayer', text ='Add New Masked Spritesheet Layer')

#panel class for shape key creation and image paint setup
class SHASPRI_PT_SheetPainting(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = 'Painting and Shape Keys'
    bl_context = 'objectmode'
    bl_category = 'Shape Spritesheet Painter'

    def draw(self, context):
        self.layout.operator('shaspri.createshapekeyforoffset', text ='Create Shape Key at UV Offset for Selected')
        self.layout.operator('shaspri.editsheetmask', text ='Edit Spritesheet Mask For Active')

#function to add a layer frame of vector displacement and color to selected
class SHASPRI_OT_AddMaskedSpriteLayer(bpy.types.Operator):
    bl_idname = "shaspri.addmaskedspritelayer"
    bl_label = "Add mask and sprite sheet"
    bl_description = "Set up images and nodes for a layer of masked sprite sheet driven by an empty"
    
    def execute(self, context):
        for candidatePaintingObject in bpy.context.selected_objects:
            if(candidatePaintingObject.type == 'MESH'):
                paintingObject = candidatePaintingObject
                objectMaterial = None
                #if there is no material create one, otherwise operate on currently active material
                if(len(paintingObject.material_slots) < 1):
                    objectMaterial = bpy.data.materials.new("shaspri_mat_" + paintingObject.name)
                    paintingObject.data.materials.append(objectMaterial)
                else:
                    objectMaterial = paintingObject.active_material
                #make sure material is using nodes
                objectMaterial.use_nodes = True
                materialNodes = objectMaterial.node_tree.nodes
                #if spritesheet folder name does not exist, create it
                spritesheetFolderPath = bpy.path.abspath(context.scene.SHASPRISpritesheetsFolder)
                #create node group if not already created
                dataNodeGroup = None
                nodeGroupOutputs = None
                nodeGroupInputs = None
                if(("shaspri_" + paintingObject.name + "_nodegroup" in bpy.data.node_groups) == False):
                    dataNodeGroup = bpy.data.node_groups.new("shaspri_" + paintingObject.name + "_nodegroup",'ShaderNodeTree')
                    nodeGroupOutputs = dataNodeGroup.nodes.new('NodeGroupOutput')
                    nodeGroupOutputs.name = "shaspri_groupoutput"
                    nodeGroupOutputs.location = [400,0]
                    nodeGroupInputs = dataNodeGroup.nodes.new('NodeGroupInput')
                    nodeGroupInputs.name = "shaspri_groupinput"
                    nodeGroupInputs.location = [-900,0]
                else:
                    dataNodeGroup = bpy.data.node_groups["shaspri_" + paintingObject.name + "_nodegroup"]
                    nodeGroupOutputs = dataNodeGroup.nodes['shaspri_groupoutput']
                    nodeGroupInputs = dataNodeGroup.nodes['shaspri_groupinput']
                #add node group to material if not already added
                materialNodeGroup = None
                if(("shaspri_NodeGroup" in materialNodes) == False):
                    materialNodeGroup = materialNodes.new('ShaderNodeGroup')
                    materialNodeGroup.node_tree = dataNodeGroup
                    materialNodeGroup.name = "shaspri_NodeGroup"
                    materialNodeGroup.location = [-400,0]
                else:
                    materialNodeGroup = materialNodes['shaspri_NodeGroup']   
                #determine number for next color mix node
                colorMixNumber = 0
                for potentialMixNode in dataNodeGroup.nodes:
                    if("shaspri_colormix_" in potentialMixNode.name):
                        colorMixNumber += 1 
                #populate node group
                spritesheetNode = None
                sheetMaskNode = None
                colorMixNode = None
                maskMultiplyNode = None
                newSpriteSheet = False
                spriteSheetName = context.scene.SHASPRISpritesheetName
                if("shaspri_" + paintingObject.name + "_" + spriteSheetName + "_sheet" in dataNodeGroup.nodes):
                    self.report({'WARNING'}, 'Spritesheet \'' + spriteSheetName + '\' already exists for \'' + paintingObject.name + '\', please choose a different spritesheet name to make a new spritesheet.')
                else:
                    if(os.path.isdir(spritesheetFolderPath) == False):
                        os.mkdir(spritesheetFolderPath)
                    spritesheetNode = dataNodeGroup.nodes.new(type='ShaderNodeTexImage')
                    spritesheetNode.name = "shaspri_" + spriteSheetName + "_sheet"
                    spritesheetNode.location = [-300,100 - (300*colorMixNumber)]
                    sheetMaskNode = dataNodeGroup.nodes.new(type='ShaderNodeTexImage')
                    sheetMaskNode.name = "shaspri_" + spriteSheetName + "_mask"
                    sheetMaskNode.location = [-300,-(300*colorMixNumber)]
                    colorMixNode = dataNodeGroup.nodes.new(type='ShaderNodeMixRGB')
                    colorMixNode.name = "shaspri_colormix_" + str(colorMixNumber)
                    colorMixNode.location = [200,-(300*colorMixNumber)]
                    maskMultiplyNode = dataNodeGroup.nodes.new(type='ShaderNodeMixRGB')
                    maskMultiplyNode.name = "shaspri_maskmultiply_" + str(colorMixNumber)
                    maskMultiplyNode.blend_type = 'MULTIPLY'
                    maskMultiplyNode.inputs[0].default_value = 1
                    maskMultiplyNode.location = [0,-(300*colorMixNumber)]
                    #create sheet and mask image textures and save them in the correct directory
                    sheetImage = bpy.data.images.new("shaspri_" + paintingObject.name + "_" + spriteSheetName + "_sheet",context.scene.SHASPRIXResolution,context.scene.SHASPRIYResolution,alpha=True)
                    sheetImage.generated_color = (0,0,0,0)
                    sheetImage.filepath = spritesheetFolderPath + "/" + sheetImage.name + ".png"
                    sheetImage.save()
                    maskImage = bpy.data.images.new("shaspri_" + paintingObject.name + "_" + spriteSheetName + "_mask",context.scene.SHASPRIXResolution,context.scene.SHASPRIYResolution,alpha=False)
                    maskImage.generated_color = (0,0,0,1)
                    maskImage.filepath = spritesheetFolderPath + "/" + maskImage.name + ".png"
                    maskImage.save()
                    #assign images to image nodes
                    spritesheetNode.image = sheetImage
                    sheetMaskNode.image = maskImage
                    #get color from group input or from previous color mix depending on number of color mix nodes
                    colorSourceNode = None
                    if(colorMixNumber == 0):
                        colorSourceNode = dataNodeGroup.nodes['shaspri_groupinput']
                    else:
                        colorSourceNode = dataNodeGroup.nodes['shaspri_colormix_' + str(colorMixNumber-1)]
                    #make sure object has uv data
                    uvLayerFinal = None
                    if(len(paintingObject.data.uv_layers) == 0):
                        paintingObject.data.uv_layers.new(name="UVMap")
                    else:
                        uvLayerFinal = paintingObject.data.uv_layers[0]
                    #create vector nodes for uv offsets
                    uvInputNode = dataNodeGroup.nodes.new(type='ShaderNodeUVMap')
                    uvInputNode.name = "shaspri_" + spriteSheetName + "_uvsource"
                    uvInputNode.uv_map = uvLayerFinal.name
                    uvInputNode.location = [-700,-(300*colorMixNumber)]
                    vectorMappingNode = dataNodeGroup.nodes.new(type='ShaderNodeMapping')
                    vectorMappingNode.name = "shaspri_" + spriteSheetName + "_uvoffset"
                    vectorMappingNode.location = [-500,-(300*colorMixNumber)]
                    #make links in nodegroup
                    dataNodeGroup.links.new(nodeGroupOutputs.inputs[0],colorMixNode.outputs[0])
                    dataNodeGroup.links.new(colorMixNode.inputs[0],maskMultiplyNode.outputs[0])
                    dataNodeGroup.links.new(colorMixNode.inputs[2],spritesheetNode.outputs[0])
                    dataNodeGroup.links.new(colorMixNode.inputs[1],colorSourceNode.outputs[0])
                    dataNodeGroup.links.new(maskMultiplyNode.inputs[1],spritesheetNode.outputs[1])
                    dataNodeGroup.links.new(maskMultiplyNode.inputs[2],sheetMaskNode.outputs[0])
                    dataNodeGroup.links.new(spritesheetNode.inputs[0],vectorMappingNode.outputs[0])
                    dataNodeGroup.links.new(vectorMappingNode.inputs[0],uvInputNode.outputs[0])
                    #if link output is enabled, attempt to connect output of node group to existing shader nodes
                    if(context.scene.SHASPRILinkOutput == True):
                        colorInputNode = None
                        for candidateNode in materialNodes:
                            #prefer common shaders over other node types, prioritised one after the other
                            if(candidateNode != materialNodeGroup):
                                if(colorInputNode != None):
                                    if not(colorInputNode.type == 'BSDF_PRINCIPLED'):
                                        if not(colorInputNode.type == 'BSDF_DIFFUSE'):
                                            if not(colorInputNode.type == 'BSDF_GLOSSY' and (candidateNode.inputs[0].type == 'RGBA' or candidateNode.inputs[0].type == 'SHADER')):
                                                colorInputNode = candidateNode
                                elif(candidateNode.inputs[0].type == 'RGBA' or candidateNode.inputs[0].type == 'SHADER'):
                                    colorInputNode = candidateNode
                        if(colorInputNode != None):
                            objectMaterial.node_tree.links.new(colorInputNode.inputs[0],materialNodeGroup.outputs[0])
                    #create empty driver
                    sceneObjects = bpy.context.scene.objects
                    uvOffsetObjectName = "shaspri_" + spriteSheetName + "_offset"
                    if((uvOffsetObjectName in sceneObjects) == False):
                        #make parent image for driver empty
                        bpy.ops.object.empty_add(type='IMAGE',rotation=(math.radians(90),0,0))
                        driverBaseObject = bpy.context.selected_objects[0]
                        driverBaseObject.name = "shaspri_" + paintingObject.name + "_" + spriteSheetName + "_imagebase"
                        driverBaseObject.empty_display_size = 50
                        driverBaseObject.data = sheetImage
                        driverBaseObject.scale = (0.05,0.05,0.05)
                        #make driver empty object
                        bpy.ops.object.empty_add(type='ARROWS',location=(0,0,0))
                        uvDriverObject = bpy.context.selected_objects[0]
                        uvDriverObject.name = "shaspri_" + paintingObject.name + "_" + spriteSheetName + "_offset"
                        uvDriverObject.show_name = True
                        uvDriverObject.parent = driverBaseObject
                        uvDriverObject.empty_display_size = 1
                        uvDriverObject.lock_location[2] = True
                        #create drivers in vector mapping node
                        driverAxisNames = ['X','Y','Z']
                        axisDrivers = vectorMappingNode.inputs[1].driver_add('default_value')
                        for axisNumber in range(0,3):
                            emptyLocationVar = axisDrivers[axisNumber].driver.variables.new()
                            emptyLocationVar.type = 'TRANSFORMS'
                            emptyLocationVar.name = 'EMPTYDRIVER' + driverAxisNames[axisNumber] + 'POS'
                            emptyLocationVar.targets[0].transform_space = 'LOCAL_SPACE'
                            emptyLocationVar.targets[0].transform_type = 'LOC_' + driverAxisNames[axisNumber]
                            emptyLocationVar.targets[0].id = uvDriverObject
                            axisDrivers[axisNumber].driver.expression = emptyLocationVar.name + '/20'
                        #switch image paint to single image
                        bpy.context.scene.tool_settings.image_paint.mode = 'IMAGE'
                #generate a base color image texture if requested
                if(context.scene.SHASPRIMakeBaseColor == True and ("shaspri_basecolor" in materialNodes) == False):
                    baseColorBitmap = bpy.data.images.new(paintingObject.name + "_" + context.scene.SHASPRIBaseColorName,context.scene.SHASPRIXResolution,context.scene.SHASPRIYResolution,alpha=True)
                    baseColorBitmap.generated_color = (0.5,0.5,0.5,1)
                    baseColorBitmap.filepath = spritesheetFolderPath + "/" + baseColorBitmap.name + ".png"
                    baseColorBitmap.save()
                    baseColorNode = materialNodes.new('ShaderNodeTexImage')
                    baseColorNode.name = "shaspri_basecolor"
                    baseColorNode.image = baseColorBitmap
                    baseColorNode.location = [-700,0]
                    objectMaterial.node_tree.links.new(materialNodeGroup.inputs[0],baseColorNode.outputs[0])
        return {'FINISHED'}
    
#function to create a driven shape key for the current uv offset
class SHASPRI_OT_CreateShapeKeyForOffset(bpy.types.Operator):
    bl_idname = "shaspri.createshapekeyforoffset"
    bl_label = "Create shape key for current uv offset"
    bl_description = "Create and edit a driven shape key for the current uv offset"
    
    def execute(self, context):
        sceneObjects = bpy.context.scene.objects
        originalSelectedObjects = bpy.context.selected_objects
        for candidatePaintingObject in originalSelectedObjects:
            #if selected object is uv offset empty, switch to the related object
            if('shaspri_' in candidatePaintingObject.name):
                if(candidatePaintingObject.name.split('_')[1] in sceneObjects):
                    candidatePaintingObject = sceneObjects[candidatePaintingObject.name.split('_')[1]]
            if(candidatePaintingObject.type == 'MESH'):
                paintingObject = candidatePaintingObject
                #check if empty driver exists
                spriteSheetName = context.scene.SHASPRISpritesheetName
                driverObjectName = "shaspri_" + paintingObject.name + "_" + spriteSheetName + "_offset"
                if((driverObjectName in sceneObjects) == False):
                    self.report({'WARNING'}, 'No driver empty found for sheet \'' + spriteSheetName + '\'. Please use \'Add New Masked Spritesheet Layer\' to set up this sheet.')
                else:
                    #get empty driver
                    uvDriverObject = sceneObjects[driverObjectName]
                    #make sure object has basis shape key and add new key for current offset
                    if(paintingObject.data.shape_keys == None):
                        paintingObject.shape_key_add(name="Basis",from_mix=False)
                    offsetShapeKey = paintingObject.shape_key_add(name="shaspri_" + spriteSheetName + "_key",from_mix=False)
                    paintingObject.active_shape_key_index += 1
                    #duplicate driver empty as location target
                    bpy.ops.object.select_all(action='DESELECT')
                    uvDriverObject.select_set(True)
                    context.view_layer.objects.active = uvDriverObject
                    bpy.ops.object.duplicate()
                    uvDriverTarget = bpy.context.active_object
                    uvDriverTarget.name = offsetShapeKey.name + "_target"
                    #return to painting mode
                    bpy.ops.object.select_all(action='DESELECT')
                    paintingObject.select_set(True)
                    context.view_layer.objects.active = paintingObject
                    #add distance driver to shape key value
                    keyValueDriver = offsetShapeKey.driver_add('value')
                    emptyLocationVar = keyValueDriver.driver.variables.new()
                    emptyLocationVar.type = 'LOC_DIFF'
                    emptyLocationVar.name = 'EMPTYDRIVER_DISTANCE'
                    emptyLocationVar.targets[0].id = uvDriverObject
                    emptyLocationVar.targets[1].id = uvDriverTarget
                    keyValueDriver.driver.expression = 'clamp(1 - (' + emptyLocationVar.name + '*10),0,1)'
        return {'FINISHED'}
    
#function to prepare nodes and texture paint for mask editing
class SHASPRI_OT_EditSheetMask(bpy.types.Operator):
    bl_idname = "shaspri.editsheetmask"
    bl_label = "Edit sheet mask"
    bl_description = "Adjust nodes and texture paint settings to edit the mask related to the active object and specified spritesheet name"
    
    def execute(self, context):
        sceneObjects = bpy.context.scene.objects
        candidatePaintingObject = bpy.context.active_object
        #if selected object is uv offset empty, switch to the related object
        if('shaspri_' in candidatePaintingObject.name):
            if(candidatePaintingObject.name.split('_')[1] in sceneObjects):
                candidatePaintingObject = sceneObjects[candidatePaintingObject.name.split('_')[1]]
        #determine if object has the required nodegroup and nodes
        if(candidatePaintingObject.type == 'MESH'):
            for candidateMaterial in candidatePaintingObject.material_slots:
                if('shaspri_NodeGroup' in candidateMaterial.material.node_tree.nodes):
                    spriteSheetName = context.scene.SHASPRISpritesheetName
                    nodeGroupTree = candidateMaterial.material.node_tree.nodes['shaspri_NodeGroup'].node_tree
                    maskImageName = "shaspri_" + candidatePaintingObject.name + "_" + spriteSheetName + "_mask"
                    if(maskImageName in bpy.data.images):
                        #change painting canvas to mask image
                        bpy.context.scene.tool_settings.image_paint.mode = 'IMAGE'
                        bpy.context.scene.tool_settings.image_paint.canvas = bpy.data.images[maskImageName]
                        bpy.context.scene.tool_settings.image_paint.brush.color = (1.0,1.0,1.0)
                        #select object with material and enter image paint mode with 3d views in solid for mask preview
                        bpy.ops.object.select_all(action='DESELECT')
                        candidatePaintingObject.select_set(True)
                        context.view_layer.objects.active = candidatePaintingObject
                        bpy.ops.paint.texture_paint_toggle()
                        for candidate3darea in bpy.context.screen.areas:
                            if(candidate3darea.type == 'VIEW_3D'):
                                candidate3darea.spaces[0].shading.type = 'SOLID'
        return {'FINISHED'}
             
#register and unregister all Shape Sprite Painter classes
shaspriClasses = (  SHASPRI_PT_LayerSetup,
                    SHASPRI_PT_SheetPainting,
                    SHASPRI_OT_AddMaskedSpriteLayer,
                    SHASPRI_OT_CreateShapeKeyForOffset,
                    SHASPRI_OT_EditSheetMask
                    )

register, unregister = bpy.utils.register_classes_factory(shaspriClasses)

if __name__ == '__main__':
    register()
