import boto


def read_file(file_name):
    """Reads an entire file and returns it as a string
    Arguments
    :param file_name: A path to a file
    """
    with open(file_name, 'r') as f:
        return f.read()


def validate_cloudformation_template(template_body):
    """Validates the JSON of a CloudFormation template produced by Troposphere
    Arguments
    :param template_body: The string representation of CloudFormation template
                          JSON
    """
    c = boto.connect_cloudformation()

    return c.validate_template(template_body=template_body)
