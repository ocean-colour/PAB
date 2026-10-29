# Create the bucket

aws s3api create-bucket --bucket pab --endpoint https://s3-west.nrp-nautilus.io

# Policy

## Generate policy

JXP copied an existing example from the ulmo Repo in nautilus/

cp ../../../ulmo/nautilus/s3_viirs_policy.json s3_pab_policy.json

### Edit Resource to point to pab instead of viirs

**Public read only.** `s3_pab_policy.json` grants `Principal: "*"` **`s3:GetObject`
only** (per N6) — anyone can read `s3://pab`, but writes/deletes go through the
bucket owner's authenticated credentials, which need no policy grant. The earlier
example also granted `PutObject`/`DeleteObject` to `*`; those were removed so that
re-applying this file can never re-open the bucket to public overwrite/wipe.

## Add policy

aws --endpoint-url https://s3-west.nrp-nautilus.io s3api put-bucket-policy --bucket pab --policy file://s3_pab_policy.json

## Check policy

aws --endpoint https://s3-west.nrp-nautilus.io s3api get-bucket-policy --bucket pab --query Policy --output text

# Users

## Check access

aws s3api  get-bucket-acl --bucket pab --endpoint https://s3-west.nrp-nautilus.io 

### Initially, I see:

{
    "Owner": {
        "DisplayName": "Xavier Prochaska",
        "ID": "profx"
    },
    "Grants": [
        {
            "Grantee": {
                "DisplayName": "Xavier Prochaska",
                "ID": "profx",
                "Type": "CanonicalUser"
            },
            "Permission": "FULL_CONTROL"
        }
    ]
}

### That shows I have full access

## Add additional users

### This is the command.  You append new users with id=USER_ID to the list

aws s3api put-bucket-acl --profile default --bucket pab --grant-full-control id=profx,id=aHR0cDovL2NpbG9nb24ub3JnL3NlcnZlckUvdXNlcnMvNTQzMjk4 --endpoint https://s3-west.nrp-nautilus.io

## Check access

aws s3api  get-bucket-acl --bucket pab --endpoint https://s3-west.nrp-nautilus.io 

