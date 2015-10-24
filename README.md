# oam-server-deployment

Amazon Web Services deployment is driven by
[Troposphere](https://github.com/cloudtools/troposphere) and
[Boto](http://boto.readthedocs.org/en/latest/).

## Dependencies

Install Troposphere and Boto into a virtualenv:

```bash
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

## CloudFormation (via Troposphere)

After the dependencies are installed, use the included `Makefile` to emit
CloudFormation JSON from the Troposphere stack definitions:

```
$ make
Template validated and written to cfn/tiler_api_stack.json
```

From there, navigate to the CloudFormation console, or use the [Amazon
CLI](https://aws.amazon.com/cli/) to launch the stack.
