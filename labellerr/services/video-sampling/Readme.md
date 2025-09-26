# LABIMP - 7672 | Subtask of LABIMP - 7569

## PROBLEM STATEMENT

As a user, I should be able to sample frames from video, so that I can create an image project via SDK

## GOAL

- create an image annotation project from a video annotation project
- sample frame are selected using multimodal llm where it has been provide with instrusion to select which frames from video

- get access to frames folder of video id | 
- how to stores frames for video | copy the frames in gcp space to another gcp project | or way to use that frame folder for source to get only selected frames

### First Version

- assume that it will only work for any one dataset for the project
- same frame folder where frame of video are stored should be the source of image project [ask from Ximi]



### ASK

- understand how video project creation work
- should work for GCS and S3 

### SUB-TASK

- which feature should be in SDK or not
- we need to created a workflow , not a bloated function, we need to make it in lEGO block
- need to decide which which feature should be in SDK for the user
- we need to create a cookbook where we attached all the SDK feature to attain a the labellin goal

- create a table where we choose which feature to be in SDK or not

### Discussion

- 