import math
import quaternion
import torch as T


# logic from : https://github.com/wzlxjtu/PositionalEncoding2D/blob/master/positionalembedding2d.py
def positionalencoding1d(d_model, length):
    """
    :param d_model: dimension of the model
    :param length: length of positions
    :return: length*d_model position matrix
    """
    if d_model % 2 != 0:
        raise ValueError("Cannot use sin/cos positional encoding with odd dim (got dim={:d})".format(d_model))
    pe = T.zeros(length, d_model)
    position = T.arange(0, length).unsqueeze(1)
    div_term = T.exp((T.arange(0, d_model, 2, dtype=T.float) * -(math.log(10000.0) / d_model)))
    pe[:, 0::2] = T.sin(position.float() * div_term)
    pe[:, 1::2] = T.cos(position.float() * div_term)
    return pe

def positionalencoding2d(d_model, height, width):
    """
    :param d_model: dimension of the model
    :param height: height of the positions
    :param width: width of the positions
    :return: d_model*height*width position matrix
    """
    if d_model % 4 != 0:
        raise ValueError("Cannot use sin/cos positional encoding with odd dimension (got dim={:d})".format(d_model))
    pe = T.zeros(d_model, height, width)
    # Each dimension use half of d_model
    d_model = int(d_model / 2)
    div_term = T.exp(T.arange(0., d_model, 2) * -(math.log(10000.0) / d_model))
    pos_w = T.arange(0., width).unsqueeze(1)
    pos_h = T.arange(0., height).unsqueeze(1)
    pe[0:d_model:2, :, :] = T.sin(pos_w * div_term).transpose(0, 1).unsqueeze(1).repeat(1, height, 1)
    pe[1:d_model:2, :, :] = T.cos(pos_w * div_term).transpose(0, 1).unsqueeze(1).repeat(1, height, 1)
    pe[d_model::2, :, :] = T.sin(pos_h * div_term).transpose(0, 1).unsqueeze(2).repeat(1, 1, width)
    pe[d_model + 1::2, :, :] = T.cos(pos_h * div_term).transpose(0, 1).unsqueeze(2).repeat(1, 1, width)
    return pe


# def get_bbox_from_kpts(kpts: T.Tensor):
    
#     # ! Not Tested
#     # TODO: different types of bboxes
    
#     assert not kpts.isnan().any(), "all keypoints have to be not nan"
    
#     # extract min and max (u,v) from keypoints
#     kpts = kpts[..., :2]
#     kpts = kpts[~(kpts.isnan().any(-1))]
#     min_ = kpts.min(0).values
#     max_ = kpts.max(0).values
#     u, v = min_
#     h, w = max_ - min_
#     return T.stack([u, v, h, w])

def nanstd(tensor : T.Tensor, dim : int, keepdim : bool = False):
    m = tensor.nanmean(dim, keepdim = True)
    s = T.sqrt(((tensor - m)**2).nanmean(dim, keepdim = keepdim))
    return s

def ms_norm(x, dim: int):
    s, m = nanstd(x, dim), x.nanmean(dim, keepdim = True)
    return (x - m) / (0.1e-4 + s)

def q_conjugate(q: T.Tensor):
    return T.stack([q[0], -q[1], -q[2], -q[3]])

def q_mult(q1: T.Tensor, q2: T.Tensor):
    w = q1[0] * q2[0] - q1[1] * q2[1] - q1[2] * q2[2] - q1[3] * q2[3]
    x = q1[0] * q2[1] + q1[1] * q2[0] + q1[2] * q2[3] - q1[3] * q2[2]
    y = q1[0] * q2[2] + q1[2] * q2[0] + q1[3] * q2[1] - q1[1] * q2[3]
    z = q1[0] * q2[3] + q1[3] * q2[0] + q1[1] * q2[2] - q1[2] * q2[1]
    return T.stack([w, x, y, z])

def qv_mult(q1: T.Tensor, v1: T.Tensor):
    q2 = T.tensor([0.0, *v1])
    return q_mult(q_mult(q1, q2), q_conjugate(q1))[1:]

def euler_to_quaternion(x: T.Tensor): # phi, theta, psi):
    sin_phi, sin_theta, sin_psi = T.sin(x / 2)
    cos_phi, cos_theta, cos_psi = T.cos(x / 2)
    qw = cos_phi * cos_theta * cos_psi + sin_phi * sin_theta * sin_psi
    qx = sin_phi * cos_theta * cos_psi - cos_phi * sin_theta * sin_psi
    qy = cos_phi * sin_theta * cos_psi + sin_phi * cos_theta * sin_psi
    qz = cos_phi * cos_theta * sin_psi - sin_phi * sin_theta * cos_psi
    return T.stack([qw, qx, qy, qz])

def quaternion_to_euler(q: T.Tensor):
    t0 = 2 * (q[0] * q[1] + q[2] * q[3])
    t1 = 1 - 2 * (q[1] * q[1] + q[2] * q[2])
    X = T.atan2(t0, t1)
    t2 = 2 * (q[0] * q[2] - q[3] * q[1])
    t2 = 1 if t2 > 1 else t2
    t2 = -1 if t2 < -1 else t2
    Y = T.asin(t2)
    t3 = 2 * (q[0] * q[3] + q[1] * q[2])
    t4 = 1 - 2 * (q[2] * q[2] + q[3] * q[3])
    Z = T.atan2(t3, t4)
    return T.stack([X, Y, Z])

def vector_angle(v1: T.Tensor, v2: T.Tensor):
    assert T.any(v1.abs() != v2.abs()), "vectors cannot be perpendicular nor exactly the same"
    return math.degrees(T.acos(v1.dot(v2) / (v1.norm() * v2.norm())))

# def rotate_to_position(input_vector: T.Tensor, output_vector: T.Tensor):
#     angle = vector_angle(input_vector, output_vector)
#     rot_axis = T.cross(input_vector, output_vector)
#     return T.Tensor(qmath.rotate3d(input_vector, angle, rot_axis))

# def extract_quat_from_rotation(input_vector: T.Tensor, output_vector: T.Tensor):
#     input_vector = input_vector / input_vector.norm()
#     output_vector = output_vector / output_vector.norm()
#     assert T.any(input_vector.abs() != output_vector.abs()), "vectors cannot be perpendicular nor exactly the same"

#     angle = vector_angle(input_vector, output_vector)
#     rot_axis = T.cross(input_vector, output_vector)

#     # p = quaternions.Quaternion(0, *input_vector)
#     axis_i, axis_j, axis_k = rot_axis
#     q = quaternions.Quaternion.from_angle(angle*0.5, (axis_i, axis_j, axis_k), degrees = False)
#     if abs(q) != 1.0:
#         q = q.versor  # Ensures q is a unit vector.
#     return T.tensor(q.components)

