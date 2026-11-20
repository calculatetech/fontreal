// Refit the upper wall of a low counter from its own contour.
bool fitLowerCounterRoof(fontreal_v3::OutlineSamples &outline, bool solid)
{
    using namespace fontreal_v3;
    const int w=4*outline.frame.width,h=4*outline.frame.height;
    const int pad=(outline.pitch-w)/2;
    const auto outside=exteriorMask(outline,64);
    const auto isOutside=[&](int x,int y) {return outside[(y+pad)*outline.pitch+x+pad];};
    struct Wall {int first=-1;int end=-1;double mass=0;double center=0;};
    std::vector<Wall> walls(w);
    for(int x=0;x<w;++x) {
        for(int y=std::max(1,int(.45*h));y<int(.78*h);) {
            if(outline.highPixel(x,y)<=64 || !isOutside(x,y-1)) {
                ++y;
                continue;
            }
            const int start=y;
            double mass=0,moment=0;
            while(y+1<h && outline.highPixel(x,y)>64) {
                const double a=outline.highPixel(x,y)/255.;
                mass+=a;
                moment+=a*(y+.5);
                ++y;
            }
            if(y==start)
                break;
            if(y+3<h && y-start<=4 && mass<=2.35 && !isOutside(x,y)
                && outline.highPixel(x,y)<=64 && outline.highPixel(x,y+1)<=64
                && outline.highPixel(x,y+2)<=64)
                walls[x]={start,y,mass,moment/mass};
        }
    }
    int begin=0,end=0;
    for(int x=0;x<w;) {
        if(walls[x].first<0) {
            ++x;
            continue;
        }
        const int first=x++;
        while(x<w && walls[x].first>=0 && std::abs(walls[x].center-walls[x-1].center)<1.24)
            ++x;
        if(x-first>end-begin){
            begin=first;
            end=x;
        }
    }
    if(end-begin<8)
        return false;
    auto fitted=outline;
    double midpoint=0;
    for(int x=begin;x<end;++x)
        midpoint+=walls[x].center/(end-begin);
    const double grid=4*(std::floor(midpoint/4)+.5);
    const double snap=std::clamp(grid-midpoint,-.85,.85);
    for(int x=begin;x<end;++x) {
        const auto &wall=walls[x];
        const double taper=std::min(1.,std::min(x-begin+.5,end-x-.5)/2.5);
        const double shift=solid ? std::clamp(grid-wall.center,-1.16,1.16) : snap;
        const double center=wall.center+.90*taper*shift;
        const double radius=.5*(wall.mass+taper*((solid ? 3.48 : 2.85)-wall.mass));
        for(int y=std::max(0,int(std::floor(center-radius)));y<std::min(h,int(std::ceil(center+radius)));++y) {
            const double support=std::clamp(std::min(y+1.,center+radius)-std::max(double(y),center-radius),0.,1.);
            auto &a=fitted.pixels[(y+pad)*outline.pitch+x+pad];
            a=std::max(a,Coverage(std::lround(255*support)));
        }
    }
    if(!hasSeveralCounters(fitted))
        return false;
    outline=std::move(fitted);
    return true;
}

fontreal_v3::Channels whiteInkRgb(fontreal_v3::Channels area, const fontreal_v3::Channels &untrimmed,
                                    const std::array<double, 3> &repair, double whiteRepair, double tinyWhite)
{
    using namespace fontreal_v3;
    for (std::size_t i = 0; i < area.size(); ++i) {
        const double a = area[i] / 255.;
        const double full = untrimmed[i] / 255.;
        const double edge = std::max(0., (a - .085) / .915);
        const double low = std::pow(edge, 1.56);
        const double gate = std::clamp((full - .24) / .40, 0., 1.);
        const double core = gate * gate * (3. - 2. * gate);
        const double target = full * (1.10 - .10 * full);
        double amount = low + (target - low) * .91 * core;
        amount += whiteRepair * repair[i] * core * (1. - amount);
        if (tinyWhite > 0. && repair[i] > 0.) {
            const double evidence = std::clamp((full - .14) / .34, 0., 1.);
            const double supported = evidence * evidence * (3. - 2. * evidence);
            amount += tinyWhite * std::sqrt(repair[i]) * supported * (1. - amount);
        }
        area[i] = encodedInk(amount, Ink::Light);
    }
    return area;
}
