#version 440

layout(location = 0) in vec2 sampleCoord;
layout(location = 0) out vec4 fragColor;
layout(binding = 1) uniform sampler2D glyphMask;

layout(std140, binding = 0) uniform buf {
    mat4 modelViewMatrix;
    mat4 projectionMatrix;
    vec2 textureScale;
    float dpr;
    vec4 color;
};

void main()
{
    vec4 coverage = texture(glyphMask, sampleCoord);
    vec3 ink = color.x > 0.5 ? coverage.rgb : vec3(coverage.a);
    fragColor = vec4(ink, coverage.a) * color.a;
}
